import json
import logging
from typing import Any, Dict, Optional
from langchain.callbacks.base import BaseCallbackHandler

from utils.request_context import get_request_context
from services.cost_monitoring_service import cost_monitoring_service
from config.cost_limits import get_model_pricing
from config.redis_cache import cache
from services.cost_service import record_cost_event, BudgetExceeded

logger = logging.getLogger(__name__)

class CostTrackingCallback(BaseCallbackHandler):
    """
    Callback handler that tracks LLM token usage and records cost.

    Behaviour:
      - on_llm_end: preferred place to capture real token usage emitted by LLMs.
      - If no token usage found, will try to read a middleware estimate cached on-disk
        (path: backend/data/cost_estimates/{request_id}.json) when request_id provided.
      - Records via project cost_monitoring_service.record_money_spent(user_id, amount)

    Usage:
      rec = CostTrackingCallback(user_id="user:123", request_id="req-abc")
      graph.add_callback(rec)  # or attach via whatever graph API you use
    """

    def __init__(self, user_id: str, request_id: Optional[str] = None):
        self.user_id = user_id
        self.request_id = request_id
        logger.info("Initialized CostTrackingCallback for user=%s request=%s", user_id, request_id)

    def _ctx_vals(self) -> Dict[str, Optional[str]]:
        """
        Return a dict with resolved user_id and request_id, preferring explicit instance values,
        then falling back to request-scoped context.
        """
        ctx = {}
        try:
            rc = get_request_context() or {}
        except Exception:
            rc = {}
        ctx_user = self.user_id or rc.get("user_id")
        ctx_req = self.request_id or rc.get("request_id")
        return {"user_id": ctx_user, "request_id": ctx_req}

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """
        Called when an LLM call finishes. `response` shape varies by framework:
          - may be an object with `llm_output` attr
          - may be a dict with keys 'llm_output', 'usage', or 'token_usage'
        """
        logger.info("CostTrackingCallback.on_llm_end called")
        try:
            llm_output = None
            if hasattr(response, "llm_output"):
                llm_output = getattr(response, "llm_output")
            elif isinstance(response, dict):
                llm_output = response.get("llm_output") or response.get("usage") or response.get("token_usage") or response

            if not llm_output:
                # nothing to do
                self._try_record_middleware_estimate()
                return

            # Normalize usage dict
            usage = None
            if isinstance(llm_output, dict):
                usage = llm_output.get("token_usage") or llm_output.get("usage") or llm_output
            else:
                # sometimes llm_output itself is usage-like
                usage = llm_output

            if not isinstance(usage, dict):
                # nothing actionable
                self._try_record_middleware_estimate()
                return

            input_tokens = int(usage.get("prompt_tokens", 0) or 0)
            output_tokens = int(usage.get("completion_tokens", 0) or 0)
            total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))
            model = (llm_output.get("model") or llm_output.get("model_name") or kwargs.get("model") or "unknown")

            exact_cost = self._calculate_cost(model, input_tokens, output_tokens)
            ctx = self._ctx_vals()
            logger.info(
                "Calculated cost for user %s request %s: $%f (tokens=%d) model=%s",
                ctx.get("user_id"),
                ctx.get("request_id"),
                exact_cost,
                total_tokens,
                    model,
            )
            record_cost_event(
                        user_id=ctx.get("user_id"),
                        request_id=ctx.get("request_id"),
                        graph_node_id=ctx.get("graph_node_id") or "search_tool",
                        agent_id=ctx.get("agent_id") or "Search Tool",
                        tool_id="tavily_search",
                        provider="tavily",
                        model_name=model,
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        total_tokens=total_tokens,
                        operation_type="retrieval",
                        successful=True,
                        cached=0,
                        note="llm",
                        prompt_id=ctx.get("prompt_id")
                    )

            #self._record_money_spent(exact_cost, model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens, total_tokens=total_tokens, source="token_usage")

        except Exception:
            logger.exception("Error in CostTrackingCallback.on_llm_end")

    # Backwards-compatible alias some frameworks use
    def on_llm_response(self, response: Any, **kwargs: Any) -> None:
        logger.info("CostTrackingCallback.on_llm_response called")
        return self.on_llm_end(response, **kwargs)

    def on_chain_end(self, chain_output: Dict[str, Any], **kwargs: Any) -> None:
        logger.info("CostTrackingCallback.on_chain_end called")
        # Chains may surface usage similarly to LLMs
        try:
            usage = chain_output.get("token_usage") if isinstance(chain_output, dict) else None
            if usage and isinstance(usage, dict):
                input_tokens = int(usage.get("prompt_tokens", 0) or 0)
                output_tokens = int(usage.get("completion_tokens", 0) or 0)
                total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))
                model = chain_output.get("model") or chain_output.get("model_name") or kwargs.get("model") or "unknown"
                exact_cost = self._calculate_cost(model, input_tokens, output_tokens)
                self._record_money_spent(exact_cost, model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens, total_tokens=total_tokens, source="token_usage")
        except Exception:
            logger.exception("Error in CostTrackingCallback.on_chain_end")

    def on_graph_end(self, graph_result: Dict[str, Any], **kwargs: Any) -> None:
        """
        Graph-level completion. Prefer graph_result token totals if provided.
        """
        logger.info("CostTrackingCallback.on_graph_end called")
        try:
            token_usage = None
            model = None
            if isinstance(graph_result, dict):
                token_usage = graph_result.get("token_usage") or graph_result.get("usage")
                model = graph_result.get("model") or graph_result.get("model_name")

            if isinstance(token_usage, dict):
                input_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
                output_tokens = int(token_usage.get("completion_tokens", 0) or 0)
                total_tokens = int(token_usage.get("total_tokens", input_tokens + output_tokens))
                exact_cost = self._calculate_cost(model, input_tokens, output_tokens)
                self._record_money_spent(exact_cost, model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens, total_tokens=total_tokens, source="token_usage")
                return

            # fallback to middleware estimate if present
            self._try_record_middleware_estimate()
        except Exception:
            logger.exception("Error in CostTrackingCallback.on_graph_end")

    # -------------------
    # Internal helpers
    # -------------------
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate exact cost from token usage using model pricing.
        """
        try:
            pricing = get_model_pricing(model)
            input_cost = (input_tokens / 1000.0) * float(pricing.get("input_cost_per_1k", 0.0))
            output_cost = (output_tokens / 1000.0) * float(pricing.get("output_cost_per_1k", 0.0))
            return round(input_cost + output_cost, 6)
        except Exception:
            logger.exception("Error calculating cost for model=%s", model)
            return 0.0

    def _try_record_middleware_estimate(self) -> None:
        """
        If no token usage was found, try to locate a middleware estimate cached to disk
        keyed by request_id. This supports the flow where middleware pre-computes an estimate.
        """
        ctx = self._ctx_vals()
        req_id = ctx.get("request_id")

        try:
            raw = cache.get(f"cost_est:{req_id}")
            if raw:
                est = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                total_cost = est.get("total_cost_usd") or est.get("total_cost") or est.get("total_cost_usd", 0)
                if total_cost:
                    logger.info("No token usage in LLM response; using middleware estimate for user %s: $%s", ctx.get("user_id"), total_cost)
                    cost_monitoring_service.record_money_spent(ctx.get("user_id"), float(total_cost))
                    return
        except Exception as e:
            logger.debug("Failed to load cached estimate for request_id %s: %s", req_id, e)

    def _record_money_spent(self, amount_usd: float) -> None:
        """
        Persist / emit the recorded cost. Prefer project service; fallback to local append-only file.
        """

        ctx = self._ctx_vals()
        user_id = ctx.get("user_id") or "unknown"

        try:
            ok = record_cost_event()
            if cost_monitoring_service is not None:
                ok = cost_monitoring_service.record_money_spent(user_id, float(amount_usd))
                if ok:
                    logger.debug("Recorded cost via cost_monitoring_service for user=%s amount=%s", user_id, amount_usd)
                    return
                logger.warning("cost_monitoring_service failed to record cost for user=%s", user_id)
        except Exception:
            logger.exception("cost_monitoring_service.record_money_spent failed")