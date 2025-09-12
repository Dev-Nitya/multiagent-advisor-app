from typing import Dict, Any, Callable, Optional, Tuple
from crewai import Crew
import logging
import time
import inspect
import uuid
import threading
from contextvars import ContextVar
from types import MethodType

from agents.agent_factory import AgentFactory
from agents.tasks.financial_advisor_task import create_financial_advisor_task
from agents.tasks.product_strategy_task import create_product_strategy_task
from agents.tasks.summary_task import create_summary_task
from agents.tasks.market_research_task import create_market_research_task
from agents.helpers.record_agent_usage import record_agent_usage
from api.schema.evaluate_startup import AgentPrompt
from utils.request_context import get_request_context, set_request_context
from utils import event_broker_redis as event_broker

logger = logging.getLogger(__name__)

# Context variable to detect top-level agent invocation in this async context.
_current_agent_invocation: ContextVar[Optional[str]] = ContextVar("current_agent_invocation", default=None)


class CrewFactory:
    _crews: Dict[str, Crew] = {}
    _wrapped_instances = set()
    _wrap_lock = threading.Lock()

    @staticmethod
    def _get_effective_prompt_id(agent_name: str) -> Optional[str]:
        try:
            ctx = get_request_context() or {}
            effective_prompt_id = ctx.get("prompt_id")
            if effective_prompt_id is None:
                effective_prompt_id = ctx.get("agent_prompt_ids", {}).get(agent_name)
            return effective_prompt_id
        except Exception as e:
            logger.info("Could not get request context for agent %s, error: %s", agent_name, e)
            return None

    # Helpers for wrapping logic -----------------------------------------------------------------

    @staticmethod
    def _candidate_callable_name(crew: Crew) -> Optional[str]:
        """
        Return the first candidate method name present on the crew that is callable.
        """
        candidate_names = [
            "kickoff", "kick_off", "run", "start", "invoke", "execute", "__call__"
        ]
        for n in candidate_names:
            if hasattr(crew, n) and callable(getattr(crew, n)):
                return n
        return None

    @staticmethod
    def _derive_request_id_from_args_kwargs(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Optional[str]:
        """
        Heuristic to extract request_id from caller-provided inputs, kwargs or request context.
        """
        try:
            # Prefer explicit dict inputs passed via common kw names
            kw_inputs = kwargs.get("inputs") or kwargs.get("input") or kwargs.get("payload")
            if isinstance(kw_inputs, dict):
                rid = kw_inputs.get("request_id") or kw_inputs.get("requestId")
                if rid:
                    return rid

            # Direct kw
            if kwargs.get("request_id"):
                return kwargs.get("request_id")

            # Positional dict as first arg (common kickoff(self, inputs_dict))
            if args and len(args) > 0 and isinstance(args[0], dict):
                rid = args[0].get("request_id") or args[0].get("requestId")
                if rid:
                    return rid

            # Fallback to request context
            ctx = get_request_context() or {}
            return ctx.get("request_id")
        except Exception:
            return None

    @staticmethod
    def _ensure_request_context_from_args_kwargs(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> None:
        """
        Ensure request_context contains user_id/request_id where possible. This helps background
        threads/tools that read ContextVar-based request context.
        """
        try:
            ctx = get_request_context() or {}
            merged = dict(ctx)

            # prefer explicit kwargs if present
            if "user_id" in kwargs and kwargs.get("user_id"):
                merged["user_id"] = kwargs.get("user_id")
            if "request_id" in kwargs and kwargs.get("request_id"):
                merged["request_id"] = kwargs.get("request_id")

            # If first positional arg is dict, merge missing values into it and update args in caller wrapper
            if args and len(args) > 0 and isinstance(args[0], dict):
                first = dict(args[0])
                if "user_id" not in first and merged.get("user_id"):
                    first["user_id"] = merged.get("user_id")
                if "request_id" not in first and merged.get("request_id"):
                    first["request_id"] = merged.get("request_id")

            # persist back
            try:
                set_request_context(merged)
            except Exception:
                # best-effort, do not raise
                pass
        except Exception:
            pass

    @staticmethod
    def _publish_agent_event(request_id: Optional[str], event: dict) -> None:
        """
        Best-effort publication to Redis-backed broker. Non-blocking and resilient.
        """
        if not request_id:
            return
        try:
            event_broker.publish_event(request_id, event)
        except Exception:
            logger.debug("Failed to publish agent event for request_id=%s: %s", request_id, event, exc_info=True)

    @staticmethod
    def _make_injecting_wrapper(fn: Callable, graph_node_id: str, agent_name: str) -> Callable:
        """
        Return a wrapper around the provided function that:
         - injects or normalizes inputs/user/request id into positional args when safe
         - ensures request context contains user_id/request_id
         - publishes agent_started and agent_finished events via Redis broker
        The wrapper preserves async/sync nature of original fn.

        Important: publishes only for the top-level invocation in the current async context to avoid
        duplicate events caused by nested/internal calls.
        """
        # freeze values to avoid late-binding/closure issues
        _agent_name = agent_name
        _graph_node_id = graph_node_id

        def _build_call_params(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Tuple[Tuple[Any, ...], Dict[str, Any], Optional[str]]:
            """
            Normalize args/kwargs and return (new_args, kwargs_to_call, derived_request_id)
            """
            try:
                kw_inputs = kwargs.get("inputs") or kwargs.get("input") or kwargs.get("payload")
                if kw_inputs is not None and isinstance(kw_inputs, dict):
                    # move inputs from kwargs into positional slot to match many kickoff signatures
                    new_kwargs = dict(kwargs)
                    new_kwargs.pop("inputs", None)
                    new_kwargs.pop("input", None)
                    new_kwargs.pop("payload", None)

                    if args and len(args) > 0:
                        # keep self/instance as first arg
                        new_args = (args[0], kw_inputs) + tuple(args[1:])
                    else:
                        new_args = (kw_inputs,) + tuple(args)

                    kwargs_to_call = new_kwargs
                else:
                    # default: preserve args and kwargs
                    new_args = args
                    kwargs_to_call = kwargs

                # if still no request_id in kwargs/inputs, try to pull from positional dict or request context
                derived_request_id = None
                if kw_inputs is not None and isinstance(kw_inputs, dict):
                    derived_request_id = kw_inputs.get("request_id") or kw_inputs.get("requestId")
                if not derived_request_id and kwargs.get("request_id"):
                    derived_request_id = kwargs.get("request_id")
                if not derived_request_id and new_args and len(new_args) > 0 and isinstance(new_args[0], dict):
                    derived_request_id = new_args[0].get("request_id") or new_args[0].get("requestId")
                if not derived_request_id:
                    ctx = get_request_context() or {}
                    derived_request_id = ctx.get("request_id")

                # ensure request_context contains values for downstream threads/tools
                try:
                    CrewFactory._ensure_request_context_from_args_kwargs(new_args, kwargs_to_call)
                except Exception:
                    pass

                return new_args, kwargs_to_call, derived_request_id
            except Exception:
                return args, kwargs, CrewFactory._derive_request_id_from_args_kwargs(args, kwargs)

        if inspect.iscoroutinefunction(fn):
            async def _async_wrapper(*args, **kwargs):
                new_args, kwargs_to_call, request_id = _build_call_params(args, kwargs)

                # determine if this is top-level invocation in this async context
                existing_invocation = _current_agent_invocation.get()
                top_level = existing_invocation is None

                invocation_id = str(uuid.uuid4())

                # set context var if top-level
                token = None
                if top_level:
                    token = _current_agent_invocation.set(invocation_id)
                    # publish started
                    CrewFactory._publish_agent_event(request_id, {
                        "type": "agent_started",
                        "agent": _agent_name,
                        "graph_node": _graph_node_id,
                        "ts": int(time.time() * 1000),
                        "invocation_id": invocation_id
                    })

                    # persist invocation_id into request context (best-effort)
                    try:
                        ctx = get_request_context() or {}
                        merged = dict(ctx)
                        merged["invocation_id"] = invocation_id
                        set_request_context(merged)
                    except Exception:
                        pass

                try:
                    result = await fn(*new_args, **kwargs_to_call)
                    return result
                finally:
                    # only the top-level publisher emits finished event and clears the context
                    if top_level:
                        try:
                            snippet = (str(result) if 'result' in locals() and result is not None else None)
                            CrewFactory._publish_agent_event(request_id, {
                                "type": "agent_finished",
                                "agent": _agent_name,
                                "graph_node": _graph_node_id,
                                "ts": int(time.time() * 1000),
                                "result_snippet": snippet,
                                "invocation_id": invocation_id
                            })
                        except Exception:
                            logger.debug("Failed to publish finished event", exc_info=True)
                        finally:
                            try:
                                if token is not None:
                                    _current_agent_invocation.reset(token)
                                    # remove invocation_id from request context if we set it
                                    try:
                                        ctx2 = get_request_context() or {}
                                        if ctx2.get("invocation_id") == invocation_id:
                                            ctx2.pop("invocation_id", None)
                                            set_request_context(ctx2)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
            return _async_wrapper
        else:
            def _sync_wrapper(*args, **kwargs):
                new_args, kwargs_to_call, request_id = _build_call_params(args, kwargs)

                existing_invocation = _current_agent_invocation.get()
                top_level = existing_invocation is None

                invocation_id = str(uuid.uuid4())

                token = None
                if top_level:
                    token = _current_agent_invocation.set(invocation_id)
                    CrewFactory._publish_agent_event(request_id, {
                        "type": "agent_started",
                        "agent": _agent_name,
                        "graph_node": _graph_node_id,
                        "ts": int(time.time() * 1000),
                        "invocation_id": invocation_id
                    })

                    # persist invocation_id into request context (best-effort) - SYNC branch
                    try:
                        ctx = get_request_context() or {}
                        merged = dict(ctx)
                        merged["invocation_id"] = invocation_id
                        set_request_context(merged)
                    except Exception:
                        pass

                try:
                    result = fn(*new_args, **kwargs_to_call)
                    return result
                finally:
                    if top_level:
                        try:
                            snippet = (str(result) if 'result' in locals() and result is not None else None)
                            CrewFactory._publish_agent_event(request_id, {
                                "type": "agent_finished",
                                "agent": _agent_name,
                                "graph_node": _graph_node_id,
                                "ts": int(time.time() * 1000),
                                "result_snippet": snippet,
                                "invocation_id": invocation_id
                            })
                        except Exception:
                            logger.debug("Failed to publish finished event", exc_info=True)
                        finally:
                            try:
                                if token is not None:
                                    _current_agent_invocation.reset(token)
                                    try:
                                        ctx2 = get_request_context() or {}
                                        if ctx2.get("invocation_id") == invocation_id:
                                            ctx2.pop("invocation_id", None)
                                            set_request_context(ctx2)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
            return _sync_wrapper

    # Core wrapper --------------------------------------------------------------------------------

    @staticmethod
    def _wrap_crew_kickoff(crew: Crew, graph_node_id: str, agent_name: str) -> Crew:
        """
        Public entry: Wrap the crew callable (kickoff/run/etc) with instrumentation that:
         - records agent usage (decorator)
         - injects user_id/request_id into inputs or request context
         - publishes agent_started/agent_finished events via Redis broker
        """
        # avoid re-wrapping same instance
        if id(crew) in CrewFactory._wrapped_instances:
            return crew

        target_name = CrewFactory._candidate_callable_name(crew)
        if not target_name:
            logger.warning(
                "Cannot instrument Crew of type %s: no known callable found",
                type(crew),
            )
            return crew

        original_callable = getattr(crew, target_name)
        orig_func = getattr(original_callable, "__func__", original_callable)
        logger.info("Wrapping Crew.%s for instrumentation (agent=%s)", target_name, agent_name)

        try:
            with CrewFactory._wrap_lock:
                # Apply usage-recording decorator first
                decorated = record_agent_usage(
                    graph_node_id_getter=lambda res, args, kwargs: graph_node_id,
                    agent_id_getter=lambda res, args, kwargs: agent_name,
                    user_id_getter=lambda res, args, kwargs: kwargs.get("user_id") or (res.get("user_id") if isinstance(res, dict) else None),
                    request_id_getter=lambda res, args, kwargs: kwargs.get("request_id") or (res.get("request_id") if isinstance(res, dict) else None),
                    provider_getter=lambda res, args, kwargs: "openai",
                    operation_type="completion",
                )(orig_func)

                # Create injecting wrapper around the decorated function (freeze values inside)
                injecting_callable = CrewFactory._make_injecting_wrapper(decorated, graph_node_id, agent_name)

                # Try binding wrapper directly to this instance
                try:
                    setattr(crew, target_name, MethodType(injecting_callable, crew))
                    CrewFactory._wrapped_instances.add(id(crew))
                    logger.debug("Instrumented %s on instance %s", target_name, type(crew).__name__)
                    return crew
                except Exception:
                    logger.info("Failed to set injecting wrapper on crew instance; attempting per-instance subclass fallback")

                    # Fallback: create a unique subclass that overrides only the target method,
                    # then assign that subclass to this instance's __class__ so other instances are unaffected.
                    try:
                        orig_type = type(crew)
                        subclass_name = f"Instrumented_{orig_type.__name__}_{id(crew)}"
                        Instrumented = type(subclass_name, (orig_type,), {target_name: injecting_callable})
                        crew.__class__ = Instrumented
                        CrewFactory._wrapped_instances.add(id(crew))
                        logger.info("Assigned per-instance subclass %s for crew instance %s", subclass_name, id(crew))
                        return crew
                    except Exception as e:
                        logger.exception("Per-instance subclass fallback failed for %s: %s", type(crew).__name__, e)
                        # If we can't subclass, leave the crew uninstrumented to avoid hangs
                        return crew

        except Exception as e:
            logger.exception("Failed to wrap Crew.%s: %s", target_name, e)
            return crew

    # Factory methods for crews --------------------------------------------------------------------

    @classmethod
    def get_market_research_crew(cls) -> Crew:
        effective_prompt_id = cls._get_effective_prompt_id('market_research')
        key = f"market_research:{effective_prompt_id or 'latest'}"
        if key not in cls._crews:
            agent = AgentFactory.get_market_research_agent(effective_prompt_id)
            task = create_market_research_task(agent)
            cls._crews[key] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._wrap_crew_kickoff(cls._crews[key], graph_node_id="market_node", agent_name="Market Research Agent")

    @classmethod
    def get_financial_analysis_crew(cls) -> Crew:
        effective_prompt_id = cls._get_effective_prompt_id('financial_advisor')
        key = f"financial_analysis:{effective_prompt_id or 'latest'}"
        if key not in cls._crews:
            agent = AgentFactory.get_financial_advisor_agent(effective_prompt_id)
            task = create_financial_advisor_task(agent)
            cls._crews[key] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._wrap_crew_kickoff(cls._crews[key], graph_node_id="finance_node", agent_name="Financial Advisor")

    @classmethod
    def get_product_strategy_crew(cls) -> Crew:
        effective_prompt_id = cls._get_effective_prompt_id('product_strategist')
        key = f"product_strategy:{effective_prompt_id or 'latest'}"
        if key not in cls._crews:
            agent = AgentFactory.get_product_strategist_agent(effective_prompt_id)
            task = create_product_strategy_task(agent)
            cls._crews[key] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._wrap_crew_kickoff(cls._crews[key], graph_node_id="product_node", agent_name="Product Strategy Agent")

    @classmethod
    def get_summary_crew(cls) -> Crew:
        effective_prompt_id = cls._get_effective_prompt_id('summary_agent')
        key = f"summary:{effective_prompt_id or 'latest'}"
        if key not in cls._crews:
            agent = AgentFactory.get_summary_agent(effective_prompt_id)
            task = create_summary_task(agent)
            cls._crews[key] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._wrap_crew_kickoff(cls._crews[key], graph_node_id="summary_node", agent_name="Summary Agent")