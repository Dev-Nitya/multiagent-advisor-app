import asyncio
from time import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Body
import logging

from agents.langgraph.advisor_graph import build_graph
from services.cost_service import BudgetExceeded
from utils.jsonExtractor import extract_json_from_raw
from api.schema.evaluate_startup import AgentPrompt, EvaluateSummary, StartupIdeaRequest, get_evaluate_openapi_responses, EVALUATE_REQUEST_EXAMPLE
from utils.prompt_sanitizer import validate_and_sanitize_idea
from utils.request_context import get_request_context, set_request_context
from config.prompt_config import is_prompt_sanitization_enabled
from services.user_prefs_service import get_prompt_sanitization_for_user
from services.prompt_registry import prompt_registry
from utils import event_broker_redis as event_broker

startup_router = APIRouter()
logger = logging.getLogger(__name__)

@startup_router.post(
        "/evaluate", 
        response_model=EvaluateSummary,
        responses=get_evaluate_openapi_responses())
async def evaluate_startup(
    request: StartupIdeaRequest = Body(..., example=EVALUATE_REQUEST_EXAMPLE)
    ):
    try:
        ctx = get_request_context() or {}

        if is_prompt_sanitization_enabled_for_request(request.user_id):
            sanitized_idea, issues = validate_and_sanitize_idea(request.idea)
            if issues:
                logger.warning(
                        "Prompt injection detected - rejecting request",
                        extra={"request_id": ctx.get("request_id") or request.request_id, "user_id": request.user_id}
                    )
                raise HTTPException(status_code=400, detail="Prompt injection detected in idea")

        request_id = None
        try:
            request_id = request.request_id
        except Exception:
            pass

        if not request_id:
            request_id = f"req-{int(time.time() * 1000)}"

        set_prompt_id(request.global_prompt_id, request.agent_prompt_ids)
        try:
            current_ctx = get_request_context() or {}
            merged = dict(current_ctx or {})
            if request.user_id:
                merged["user_id"] = request.user_id
            if request_id:
                merged["request_id"] = request_id
            try:
                set_request_context(merged)
            except Exception:
                pass
        except Exception:
            pass

        graph = build_graph()
        # start background task and return immediately with request_id so client can subscribe
        asyncio.create_task(delegate_graph_run_to_background(graph, request.user_id, request_id, sanitized_idea))

        logger.info(f"Invoking graph for request_id: {request_id}, user_id: {request.user_id}")

        return {
            "market_verdict": "",
            "financial_verdict": "",
            "product_verdict": "",
            "final_recommendation": "",
            "rationale": "",
            "confidence_score": 0,
            "request_id": request_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def process_final_summary(final_summary) -> Optional[EvaluateSummary]:
    """Process the final summary to extract structured data"""
    if not final_summary or not isinstance(final_summary, dict):
        return None
    
    # Get the raw content from tasks_output
    tasks_output = final_summary.get('tasks_output', [])
    if not tasks_output:
        return None
    
    raw_content = tasks_output[0].get('raw', '')
    
    # Extract JSON from the raw content
    extracted_data = extract_json_from_raw(raw_content)
    
    if extracted_data:
        return {
            "market_verdict": extracted_data.get("market_verdict", ""),
            "financial_verdict": extracted_data.get("financial_verdict", ""),
            "product_verdict": extracted_data.get("product_verdict", ""),
            "final_recommendation": extracted_data.get("final_recommendation", ""),
            "rationale": extracted_data.get("rationale", ""),
            "confidence_score": extracted_data.get("confidence_score", 0)
        }
    
    # Fallback to raw text if JSON extraction fails
    return {
        "summary": raw_content,
        "final_recommendation": "uncertain",
        "confidence_score": 0
    }

def is_prompt_sanitization_enabled_for_request(user_id: Optional[str]) -> bool:
    """
    Resolve whether prompt sanitization should be applied for this request.

    Priority:
      1. Per-user preference (database) if user_id provided and preference set.
      2. Application-level default from prompt_config.
      3. Safe fallback: True (enabled).

    Returns True if sanitization should be applied.
    """
    try:
        if user_id:
            user_pref = get_prompt_sanitization_for_user(user_id)
            if user_pref is not None:
                return bool(user_pref)
    except Exception:
        # If DB lookup fails, fall through to app-level config
        pass

    try:
        return bool(is_prompt_sanitization_enabled())
    except Exception:
        return True

def set_prompt_id(prompt_id, agent_prompt_ids) -> str | None:
    """Helper to get prompt_id from request context if available."""
    
    effective_prompt_id = None
    validated_agent_prompt_ids: Optional[AgentPrompt] = None

    if prompt_id:
        prompt = prompt_registry.get_prompt_by_id(prompt_id)
        if prompt:
            effective_prompt_id = prompt_id
        else:
            logger.warning(f"Provided prompt_id {prompt_id} not found in registry; ignoring.")
            effective_prompt_id = None
    
    # per-agent mapping: validate each mapping entry
    if agent_prompt_ids:
        prompt_dict = agent_prompt_ids.dict()
        validated_agent_prompt_ids = {}
        for agent_key, agent_prompt_id in prompt_dict.items():
            prompt = prompt_registry.get_prompt_by_id(agent_prompt_id)
            if prompt:
                validated_agent_prompt_ids[agent_key] = agent_prompt_id
            else:
                logger.warning(
                    f"Provided agent_prompt_id {agent_prompt_id} for agent {agent_key} not found in registry; rejecting request."
                )
                raise HTTPException(status_code=400, detail=f"Invalid agent_prompt_id {agent_prompt_id} for agent {agent_key}")

     # fallback to latest prompt in registry if nothing provided
    if not effective_prompt_id and not validated_agent_prompt_ids:
        db_latest_prompt_id = prompt_registry.get_latest_prompt_id()
        if db_latest_prompt_id:
            effective_prompt_id = db_latest_prompt_id
        else:
            logger.warning("No prompts found in registry to set prompt_id from.")

    # merge into request context
    current_ctx = get_request_context() or {}
    merged = dict(current_ctx or {})
    if effective_prompt_id:
        merged["prompt_id"] = effective_prompt_id
    if validated_agent_prompt_ids:
        merged["agent_prompt_ids"] = validated_agent_prompt_ids

    try:
        set_request_context(merged)
    except Exception:
        pass


async def delegate_graph_run_to_background(graph, user_id, request_id, sanitized_idea):
    try:
        def _run():
            try:
                result = graph.invoke({"idea": sanitized_idea, "user_id": user_id, "request_id": request_id})

                # try to read invocation_id from request context (set by crew wrapper for top-level invocation)
                try:
                    ctx_after = get_request_context() or {}
                    invocation_id = ctx_after.get("invocation_id")
                except Exception:
                    invocation_id = None

                try:
                    event_broker.publish_event(request_id, {
                        "type": "final_result",
                        "payload": result,
                        "invocation_id": invocation_id
                    })
                except Exception:
                    pass
            except Exception as e:
                try:
                    event_broker.publish_event(request_id, {"type": "error", "message": str(e)})
                except Exception:
                    pass

        # run blocking invoke in threadpool
        await asyncio.to_thread(_run)
    finally:
        try:
            # include invocation id if available in this thread's request context
            try:
                ctx_fin = get_request_context() or {}
                invocation_id_fin = ctx_fin.get("invocation_id")
            except Exception:
                invocation_id_fin = None

            event_broker.publish_event(request_id, {"type": "__COMPLETE__", "invocation_id": invocation_id_fin})
        except Exception:
            pass

