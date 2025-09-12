"""
LLM Manager with connection pooling for efficient resource management
"""
import os
import logging
from typing import Dict, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseLLM
from langchain.callbacks.base import BaseCallbackHandler
import httpx
from threading import Lock

from utils.request_context import get_request_context
from services.cost_service import record_cost_event, BudgetExceeded

logger = logging.getLogger(__name__)


class _CostTrackingHandler(BaseCallbackHandler):
    """
    LangChain callback that records token usage into cost_service whenever an LLM run completes.
    Best-effort: does not break on failure. Raises BudgetExceeded to propagate enforcement.
    """
    def __init__(
        self,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        graph_node_id: Optional[str] = "{{DEFAULT_GRAPH_NODE}}",
        agent_id: Optional[str] = "unknown_agent",
    ):
        self.user_id = user_id
        self.request_id = request_id
        self.graph_node_id = graph_node_id
        self.agent_id = agent_id

    def on_llm_start(self, run: Any, **kwargs) -> None:
        """Capture request-scoped context at the start of the LLM call.
        This snapshot will be attached to the run metadata so that on_llm_end
        can use it even if it executes in a different thread/context.
        """
        try:
            ctx = get_request_context() or {}
            captured = {
                "user_id": ctx.get("user_id"),
                "request_id": ctx.get("request_id"),
                "graph_node_id": ctx.get("graph_node_id"),
                "agent_id": ctx.get("agent_id"),
            }
            # Try to attach to run.extra in both dict and object shapes
            if isinstance(run, dict):
                extra = run.setdefault("extra", {})
                extra["captured_request_context"] = captured
            else:
                try:
                    extra = getattr(run, "extra", None)
                    if extra is None:
                        setattr(run, "extra", {"captured_request_context": captured})
                    else:
                        extra["captured_request_context"] = captured
                except Exception:
                    # best-effort, don't break
                    pass
        except Exception:
            logger.exception("_CostTrackingHandler.on_llm_start failed to capture request context")

    def on_llm_end(self, run: Any, **kwargs) -> None:
        try:
            # Prefer captured context at start (works across threads)
            captured_ctx = None
            try:
                if isinstance(run, dict):
                    captured_ctx = (run.get("extra") or {}).get("captured_request_context") or kwargs.get("captured_request_context")
                else:
                    captured_ctx = (getattr(run, "extra", None) or {}).get("captured_request_context") or kwargs.get("captured_request_context")
            except Exception:
                captured_ctx = None

            # live context as fallback
            live_ctx = get_request_context() or {}

            user_id = (captured_ctx and captured_ctx.get("user_id")) or live_ctx.get("user_id") or self.user_id
            request_id = (captured_ctx and captured_ctx.get("request_id")) or live_ctx.get("request_id") or self.request_id
            graph_node_id = (captured_ctx and captured_ctx.get("graph_node_id")) or live_ctx.get("graph_node_id") or self.graph_node_id or "{{DEFAULT_GRAPH_NODE}}"
            agent_id = (captured_ctx and captured_ctx.get("agent_id")) or live_ctx.get("agent_id") or self.agent_id or "unknown_agent"

            # Helper: robust extraction of llm usage/token info from different run shapes
            def _extract_token_usage(run_obj, kw):
                # Common shapes to inspect
                candidates = []
                try:
                    if isinstance(run_obj, dict):
                        candidates.append(run_obj)
                        candidates.append(run_obj.get("extra") or {})
                        candidates.append(run_obj.get("llm_output") or {})
                        candidates.append(run_obj.get("response") or {})
                    else:
                        candidates.append(getattr(run_obj, "llm_output", {}) or {})
                        candidates.append(getattr(run_obj, "extra", {}) or {})
                        candidates.append(getattr(run_obj, "response", {}) or {})
                except Exception:
                    pass

                # Also include kwargs that some wrappers pass
                if kw:
                    candidates.append(kw.get("response") or {})
                    candidates.append(kw.get("extra") or {})

                # Flatten search for known usage keys
                for c in candidates:
                    if not isinstance(c, dict):
                        # try to coerce object with attrs to dict-like access
                        try:
                            c = dict(getattr(c, "__dict__", {}) or {})
                        except Exception:
                            continue
                    for key in ("token_usage", "usage", "tokens", "tokenCounts", "token_usage_summary"):
                        tu = c.get(key)
                        if tu:
                            return tu
                    # Some providers nest usage under 'usage' inside a 'usage' object
                    if c.get("usage") and isinstance(c.get("usage"), dict):
                        return c.get("usage")
                return None

            tu = _extract_token_usage(run, kwargs)
            if not tu:
                # nothing to record -- capture a small, redacted snapshot to help tuning the extractor
                try:
                    def _snapshot(obj):
                        try:
                            if obj is None:
                                return None
                            if isinstance(obj, dict):
                                return {"type": "dict", "keys": list(obj.keys())}
                            if isinstance(obj, str):
                                return {"type": "str", "len": len(obj)}
                            if isinstance(obj, list):
                                return {"type": "list", "len": len(obj)}
                            return {"type": type(obj).__name__}
                        except Exception:
                            return {"type": "unknown"}

                    extra = None
                    llm_output = None
                    response_obj = None
                    if isinstance(run, dict):
                        extra = run.get("extra")
                        llm_output = run.get("llm_output")
                        response_obj = run.get("response")
                    else:
                        extra = getattr(run, "extra", None)
                        llm_output = getattr(run, "llm_output", None)
                        response_obj = getattr(run, "response", None)

                    snapshot = {
                        "run_type": type(run).__name__,
                        "extra": _snapshot(extra),
                        "llm_output": _snapshot(llm_output),
                        "response": _snapshot(response_obj),
                        "kwargs_keys": list(kwargs.keys())
                    }
                    logger.debug("_CostTrackingHandler: no token usage found; snapshot=%s", snapshot)
                except Exception:
                    logger.debug("_CostTrackingHandler: no token usage and failed to build snapshot")
                return

            # Normalise token fields
            prompt = tu.get("prompt_tokens") or tu.get("prompt") or tu.get("input_tokens") or tu.get("prompt_token_count")
            completion = tu.get("completion_tokens") or tu.get("completion") or tu.get("output_tokens") or tu.get("completion_token_count")
            total = tu.get("total_tokens") or tu.get("total") or tu.get("tokens")
            cached = bool(tu.get("cached_prompt_tokens", 0) or tu.get("cached", False))

            # Try to infer model name
            model = None
            try:
                model = getattr(getattr(run, "llm", None), "model_name", None) or getattr(getattr(run, "llm", None), "name", None) or (tu.get("model") or tu.get("model_name"))
            except Exception:
                model = tu.get("model") or tu.get("model_name")

            try:                
                prompt_id = live_ctx.get("prompt_id")

                record_cost_event(
                    user_id=user_id,
                    request_id=request_id,
                    graph_node_id=graph_node_id,
                    agent_id=agent_id,
                    tool_id=None,
                    provider="openai",
                    model_name=model,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    operation_type="completion",
                    successful=True,
                    cached=cached,
                    note="llm_callback_recorded",
                    prompt_id=prompt_id
                )
            except BudgetExceeded:
                logger.warning("BudgetExceeded in _CostTrackingHandler for user=%s", user_id)
                raise
            except Exception:
                logger.exception("Failed to record cost in _CostTrackingHandler")
        except Exception:
            logger.exception("_CostTrackingHandler.on_llm_end encountered unexpected error")


class LLMManager:
    """
    Singleton LLM manager that provides connection pooling and reuse of LLM instances
    """
    _instance = None
    _lock = Lock()
    _llm_instances: Dict[str, BaseLLM] = {}
    _http_client: Optional[httpx.Client] = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self._initialize_http_client()
            self.initialized = True

    def _initialize_http_client(self):
        """Initialize HTTP client with connection pooling"""

        # Event hook to inject request-id header per outgoing request using request-scoped context
        def _inject_request_id(request: httpx.Request):
            try:
                ctx = get_request_context() or {}
                req_id = ctx.get("request_id")
                if req_id:
                    # Preserve existing header if present, otherwise set it
                    if "x-request-id" not in request.headers:
                        request.headers["x-request-id"] = req_id
            except Exception:
                return

        # Event hook to inject user-id header per outgoing request using request-scoped context
        def _inject_user_id(request: httpx.Request):
            try:
                ctx = get_request_context() or {}
                user_id = ctx.get("user_id")
                if user_id:
                    # Preserve existing header if present, otherwise set it
                    if "x-user-id" not in request.headers:
                        request.headers["x-user-id"] = user_id
            except Exception:
                return

        self._http_client = httpx.Client(
            # Connection pooling settings
            limits=httpx.Limits(
                max_keepalive_connections=20,  # Keep 20 connections alive
                max_connections=100,           # Max total connections
                keepalive_expiry=30.0          # Keep connections alive for 30 seconds
            ),
            # Timeout settings
            timeout=httpx.Timeout(
                connect=10.0,   # Connection timeout
                read=60.0,      # Read timeout
                write=10.0,     # Write timeout
                pool=5.0        # Pool timeout
            ),
            # Retry settings
            transport=httpx.HTTPTransport(retries=2),
            event_hooks={"request": [_inject_request_id, _inject_user_id]}
        )

    @classmethod
    def get_openai_llm(
        cls,
        model_name: str = "gpt-3.5-turbo",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> ChatOpenAI:
        """Get a pooled OpenAI LLM instance"""
        instance = cls()
        key = f"openai_{model_name}_{temperature}_{max_tokens}"

        print(f'Choosing model name for this run: {model_name}')

        if key not in instance._llm_instances:
            with cls._lock:
                if key not in instance._llm_instances:
                    # Create OpenAI LLM with pooled HTTP client
                    llm = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        max_retries=2,
                        request_timeout=60,
                        # Use our pooled HTTP client
                        http_client=instance._http_client,
                        # Connection reuse settings
                        streaming=False,  # Disable streaming for better pooling
                    )
                    # Attach cost-tracking callback (best-effort)
                    try:
                        ctx = get_request_context() or {}
                        handler = _CostTrackingHandler(
                            user_id=ctx.get("user_id"),
                            request_id=ctx.get("request_id"),
                            graph_node_id=ctx.get("graph_node_id") or "{{DEFAULT_GRAPH_NODE}}",
                            agent_id=ctx.get("agent_id") or "unknown_agent",
                        )
                        # LangChain may expose a callbacks list or accept attribute assignment
                        if hasattr(llm, "callbacks") and isinstance(getattr(llm, "callbacks"), list):
                            llm.callbacks.append(handler)
                        else:
                            # fallback: set attribute
                            existing = getattr(llm, "callbacks", None)
                            if existing is None:
                                setattr(llm, "callbacks", [handler])
                            else:
                                try:
                                    existing.append(handler)
                                except Exception:
                                    setattr(llm, "callbacks", [handler])
                    except Exception:
                        logger.exception("Failed to attach CostTrackingHandler to ChatOpenAI instance")
                    instance._llm_instances[key] = llm

        return instance._llm_instances[key]
    
    @classmethod
    def get_llm_from_settings(cls, model_settings: Optional[Dict[str, Any]] = None) -> BaseLLM:
        """
        Build/return an LLM instance based on a stored model_settings dict.

        Expected keys in model_settings (any subset):
          - provider: "openai" | "anthropic" (optional, defaults to openai)
          - model_name: provider model identifier (e.g. "gpt-4", "gpt-3.5-turbo")
          - temperature: float
          - max_tokens: int
          - any other keys are ignored for now

        Falls back to get_default_llm() when settings are missing or unrecognised.
        """
        if not model_settings:
            return cls.get_default_llm()

        provider = (model_settings.get("provider") or "openai").lower()
        model_name = model_settings.get("model_name")
        temperature = model_settings.get("temperature")
        max_tokens = model_settings.get("max_tokens")

        # Normalize simple cases where model_name implies provider
        if not provider and isinstance(model_name, str) and "claude" in model_name.lower():
            provider = "anthropic"

        try:
            if provider == "openai":
                # Use explicit values when provided, otherwise let get_openai_llm defaults apply
                kwargs = {}
                if model_name:
                    kwargs["model_name"] = model_name
                if temperature is not None:
                    kwargs["temperature"] = float(temperature)
                if max_tokens is not None:
                    kwargs["max_tokens"] = int(max_tokens)

                return cls.get_openai_llm(**kwargs)
            elif provider == "anthropic":
                # Use anthropic helper if available; otherwise fall back to OpenAI
                anthropic_fn = getattr(cls, "get_anthropic_llm", None)
                if callable(anthropic_fn):
                    kwargs = {}
                    if model_name:
                        kwargs["model_name"] = model_name
                    if temperature is not None:
                        kwargs["temperature"] = float(temperature)
                    if max_tokens is not None:
                        kwargs["max_tokens"] = int(max_tokens)
                    return anthropic_fn(**kwargs)
                else:
                    # graceful fallback
                    logger.warning("Anthropic requested in model_settings but get_anthropic_llm not available; falling back to OpenAI")
                    return cls.get_openai_llm(model_name=model_name or "gpt-3.5-turbo", temperature=temperature or 0.1, max_tokens=max_tokens)
            else:
                # Unknown provider: fallback to default LLM
                logger.warning("Unknown provider '%s' in model_settings; using default LLM", provider)
                return cls.get_default_llm()
        except Exception:
            logger.exception("Failed to build LLM from model_settings, falling back to default LLM")
            return cls.get_default_llm()

    @classmethod
    def get_default_llm(cls, **kwargs) -> BaseLLM:
        """Get the default LLM based on available API keys"""
        if os.getenv("OPENAI_API_KEY"):
            return cls.get_openai_llm(**kwargs)
        elif os.getenv("ANTHROPIC_API_KEY"):
            return cls.get_anthropic_llm(**kwargs)
        else:
            # Fallback to OpenAI (will raise error if no key)
            return cls.get_openai_llm(**kwargs)

    @classmethod
    def get_fast_llm(cls) -> BaseLLM:
        """Get a fast, low-cost LLM for simple tasks"""
        if os.getenv("OPENAI_API_KEY"):
            return cls.get_openai_llm(model_name="gpt-3.5-turbo", temperature=0.1)
        else:
            return cls.get_default_llm(temperature=0.1)

    @classmethod
    def get_smart_llm(cls) -> BaseLLM:
        """Get a more capable LLM for complex tasks"""
        if os.getenv("OPENAI_API_KEY"):
            return cls.get_openai_llm(model_name="gpt-4", temperature=0.1)
        elif os.getenv("ANTHROPIC_API_KEY"):
            return cls.get_anthropic_llm(model_name="claude-3-sonnet-20240229", temperature=0.1)
        else:
            return cls.get_default_llm(temperature=0.1)

    @classmethod
    def close_connections(cls):
        """Close all pooled connections (call on app shutdown)"""
        instance = cls()
        if instance._http_client:
            instance._http_client.close()
            instance._http_client = None
        instance._llm_instances.clear()

    @classmethod
    def get_pool_stats(cls) -> Dict[str, int]:
        """Get connection pool statistics"""
        instance = cls()
        return {
            "cached_llm_instances": len(instance._llm_instances),
            "http_client_active": 1 if instance._http_client else 0,
        }