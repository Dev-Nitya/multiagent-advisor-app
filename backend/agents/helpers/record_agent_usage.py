import functools
import logging
import inspect
from typing import Callable, Any, Optional

from services.cost_service import record_cost_event, BudgetExceeded
from utils.request_context import set_request_context, get_request_context

logger = logging.getLogger(__name__)

def _extract_from_args_or_kwargs(args, kwargs, key: str):
    # If kickoff was called as kickoff(inputs_dict), user info may live in one of the first positional args
    try:
        # check explicit kwargs first
        if key in kwargs and kwargs.get(key) is not None:
            return kwargs.get(key)
        # scan the first few positional args for a dict containing the key
        for a in (args or [])[:3]:
            if isinstance(a, dict) and a.get(key) is not None:
                return a.get(key)
    except Exception:
        pass
    return None

def record_agent_usage(
    *,
    graph_node_id_getter: Callable[[Any, tuple, dict], Optional[str]] = lambda res, args, kwargs: (_extract_from_args_or_kwargs(args, kwargs, "graph_node_id") or kwargs.get("graph_node_id") or (res.get("graph_node_id") if isinstance(res, dict) else None)),
    agent_id_getter: Callable[[Any, tuple, dict], Optional[str]] = lambda res, args, kwargs: (_extract_from_args_or_kwargs(args, kwargs, "agent_id") or kwargs.get("agent_id") or (res.get("agent_id") if isinstance(res, dict) else None)),
    user_id_getter: Callable[[Any, tuple, dict], Optional[str]] = lambda res, args, kwargs: (_extract_from_args_or_kwargs(args, kwargs, "user_id") or kwargs.get("user_id") or (res.get("user_id") if isinstance(res, dict) else None)),
    request_id_getter: Callable[[Any, tuple, dict], Optional[str]] = lambda res, args, kwargs: (_extract_from_args_or_kwargs(args, kwargs, "request_id") or kwargs.get("request_id") or (res.get("request_id") if isinstance(res, dict) else None)),
    provider_getter: Callable[[Any, tuple, dict], Optional[str]] = lambda res, args, kwargs: "openai",
    operation_type: Optional[str] = None
):
    """
    Decorator to attach to functions that return agent/tool result dicts containing token_usage.
    The decorated function must return a dict-like object where token usage may live under 'token_usage' or 'tokens'.
    Supports both sync and async functions.
    """
    def _decor(fn: Callable[..., Any]):
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            prev_ctx = get_request_context() or {}
            try:
                derived_user = _extract_from_args_or_kwargs(args, kwargs, "user_id") or kwargs.get("user_id")
                derived_request = _extract_from_args_or_kwargs(args, kwargs, "request_id") or kwargs.get("request_id")
                derived_graph = _extract_from_args_or_kwargs(args, kwargs, "graph_node_id") or kwargs.get("graph_node_id")
                derived_agent = _extract_from_args_or_kwargs(args, kwargs, "agent_id") or kwargs.get("agent_id")

                new_ctx = dict(prev_ctx or {})
                if derived_user:
                    new_ctx["user_id"] = derived_user
                if derived_request:
                    new_ctx["request_id"] = derived_request
                if derived_graph:
                    new_ctx["graph_node_id"] = derived_graph
                if derived_agent:
                    new_ctx["agent_id"] = derived_agent

                try:
                    set_request_context(new_ctx)
                except Exception:
                    pass

                result = fn(*args, **kwargs)

                try:
                    tokens = extract_from_args(args)
                    token_usage = {}
                    for tu in tokens:
                        token_usage = tu["token_usage"]
                        token_usage = normalize_token_usage(token_usage)

                    # access individual values
                    total_tokens = token_usage.get('total_tokens', 0)
                    prompt_tokens = token_usage.get('prompt_tokens', 0)
                    completion_tokens = token_usage.get('completion_tokens', 0)

                    prompt = prompt_tokens
                    completion = completion_tokens
                    total = total_tokens
                    cached = bool(token_usage.get("cached_prompt_tokens", 0))
                    successful_requests = token_usage.get("successful_requests")
                    note = ""
                    if successful_requests:
                        note = (note + ("; " if note else "") + "aggregated_over_successful_requests")

                    try:
                            
                        prompt_id = prev_ctx.get("prompt_id")

                        model_name = 'gpt-3.5-turbo'
                        try:
                            if prompt_id:
                                from services.prompt_registry import prompt_registry
                                prompt_details = prompt_registry.get_prompt_by_id(prompt_id)

                                # handle both dict results and ORM Prompt instances
                                ms = None
                                if isinstance(prompt_details, dict):
                                    ms = prompt_details.get("model_settings")
                                else:
                                    # ORM/other object: try attribute access
                                    ms = getattr(prompt_details, "model_settings", None)

                                # if model_settings stored as JSON string, attempt to parse
                                if isinstance(ms, str):
                                    try:
                                        import json
                                        ms = json.loads(ms)
                                    except Exception:
                                        pass

                                if isinstance(ms, dict) and ms.get("model_name"):
                                    model_name = ms.get("model_name")
                        except Exception:
                            pass
                        
                        record_cost_event(
                            user_id=new_ctx.get("user_id"),
                            request_id=new_ctx.get("request_id"),
                            graph_node_id=graph_node_id_getter(result, args, kwargs) or "{{DEFAULT_GRAPH_NODE}}",
                            agent_id=agent_id_getter(result, args, kwargs) or "unknown_agent",
                            tool_id=None,
                            provider=provider_getter(result, args, kwargs),
                            model_name=model_name,
                            prompt_tokens=prompt,
                            completion_tokens=completion,
                            total_tokens=total,
                            operation_type=operation_type or "completion",
                            successful=True,
                            cached=cached,
                            note=note,
                            prompt_id=prompt_id
                        )
                    except BudgetExceeded:
                        logger.warning("Budget exceeded while recording usage")
                        raise
                    except Exception:
                        logger.exception("Failed to record cost event from decorator")

                except Exception:
                    logger.exception("Instrumentation decorator stumbled")

                return result
            finally:
                try:
                    set_request_context(prev_ctx)
                except Exception:
                    pass
        return _wrapped

    return _decor

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

CREW_ID_RE = re.compile(r"id=([0-9a-fA-F-]+)")

def extract_crew_id(crew_obj: Any) -> Optional[str]:
    """
    Try to extract a crew id from the first tuple element.
    Accepts either an object with attribute `id` or a string like "Crew(id=...)"
    """
    # 1) object with attribute
    try:
        crew_id = getattr(crew_obj, "id", None)
        if crew_id:
            return str(crew_id)
    except Exception:
        pass

    # 2) string representation
    s = str(crew_obj)
    m = CREW_ID_RE.search(s)
    if m:
        return m.group(1)
    return None

def normalize_token_usage(tu: Dict[str, Any]) -> Dict[str, int]:
    """
    Ensure keys exist and cast to ints (fallback to 0).
    """
    return {
        "total_tokens": int(tu.get("total_tokens", 0) or 0),
        "prompt_tokens": int(tu.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(tu.get("completion_tokens", 0) or 0),
        "cached_prompt_tokens": int(tu.get("cached_prompt_tokens", 0) or 0),
        "successful_requests": int(tu.get("successful_requests", 0) or 0),
    }

def extract_token_usage_from_args(arg_tuple: Tuple[Any, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Given one args tuple like (Crew(...), {...}), return a list of extracted token_usage events.
    Each event is a normalized dict:
      {
        "crew_id": str | None,
        "node_key": "market_insights" | ...,
        "agent": <agent name if present>,
        "request_id": <request_id if present>,
        "user_id": <user_id if present>,
        "token_usage": {total_tokens, prompt_tokens, completion_tokens, ...},
        "raw_block": <the nested dict for context>
      }
    """
    crew_obj, payload = arg_tuple
    crew_id = extract_crew_id(crew_obj)

    events: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return events

    # common fields that may be at payload level
    request_id = payload.get("request_id")
    user_id = payload.get("user_id")

    # iterate nested keys like 'market_insights', 'financial_insights', etc.
    for node_key, node_val in payload.items():
        # skip top-level keys that are not dicts or obvious metadata
        if not isinstance(node_val, dict):
            continue

        # token_usage may be present directly
        tu = node_val.get("token_usage")
        if tu and isinstance(tu, dict):
            events.append({
                "crew_id": crew_id,
                "node_key": node_key,
                "agent": node_val.get("agent") or node_key,
                "request_id": request_id,
                "user_id": user_id,
                "token_usage": normalize_token_usage(tu),
                "raw_block": node_val
            })
            continue

        # sometimes tokens may be embedded in tasks_output entries (rare); search inside
        tasks = node_val.get("tasks_output")
        if isinstance(tasks, list):
            for t in tasks:
                if isinstance(t, dict):
                    # check nested token_usage inside task
                    nested_tu = t.get("token_usage") or t.get("usage")
                    if isinstance(nested_tu, dict):
                        events.append({
                            "crew_id": crew_id,
                            "node_key": node_key,
                            "agent": t.get("agent") or node_val.get("agent") or node_key,
                            "request_id": request_id,
                            "user_id": user_id,
                            "token_usage": normalize_token_usage(nested_tu),
                            "raw_block": t
                        })
        # if nothing found, continue (we don't raise)
    return events

def extract_from_args(arg: Tuple[Any, Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        evs = extract_token_usage_from_args(arg)
        return evs
    except Exception as e:
        # safe: skip problematic arg but keep going
        results = {
            "crew_id": extract_crew_id(arg[0]) if len(arg) > 0 else None,
            "node_key": None,
            "agent": None,
            "request_id": arg[1].get("request_id") if len(arg) > 1 and isinstance(arg[1], dict) else None,
            "user_id": arg[1].get("user_id") if len(arg) > 1 and isinstance(arg[1], dict) else None,
            "token_usage": {"error": str(e)},
            "raw_block": None,
        }
        return results
