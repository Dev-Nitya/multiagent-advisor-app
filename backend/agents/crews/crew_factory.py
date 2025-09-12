from typing import Dict
from crewai import Crew
import logging

from agents.agent_factory import AgentFactory
from agents.tasks.financial_advisor_task import create_financial_advisor_task
from agents.tasks.product_strategy_task import create_product_strategy_task
from agents.tasks.summary_task import create_summary_task
from agents.tasks.market_research_task import create_market_research_task
from agents.helpers.record_agent_usage import record_agent_usage
from api.schema.evaluate_startup import AgentPrompt
from utils.request_context import get_request_context

logger = logging.getLogger(__name__)

class CrewFactory:
    _crews: Dict[str, Crew] = {}
    _wrapped_instances = set()

    def _get_effective_prompt_id(agent_name: str) -> str | None:
        try:
            ctx = get_request_context() or {}
            effective_prompt_id = ctx.get("prompt_id")
            if effective_prompt_id is None:
                effective_prompt_id = ctx.get("agent_prompt_ids", {}).get(agent_name)
            return effective_prompt_id
        except Exception as e:
            logger.info(f"Could not get request context for agent {agent_name}, error: {e}")
            return None

    @staticmethod
    def _wrap_crew_kickoff(crew: Crew, graph_node_id: str, agent_name: str):
        # avoid re-wrapping same instance
        if id(crew) in CrewFactory._wrapped_instances:
            return crew

        # Detect the crew method we should wrap (common names)
        candidate_names = [
            "kickoff", "kick_off", "run", "start", "invoke", "execute", "__call__"
        ]
        target_name = None
        for n in candidate_names:
            if hasattr(crew, n) and callable(getattr(crew, n)):
                target_name = n
                break

        if not target_name:
            logger.warning(
                "Cannot instrument Crew of type %s: no known callable found (%s)",
                type(crew),
                candidate_names,
            )
            return crew

        original_callable = getattr(crew, target_name)
        # if bound method, extract underlying function so it can be set on the class
        orig_func = getattr(original_callable, "__func__", original_callable)
        logger.info("Wrapping Crew.%s for instrumentation (agent=%s)", target_name, agent_name)

        try:
            decorated = record_agent_usage(
                graph_node_id_getter=lambda res, args, kwargs: graph_node_id,
                agent_id_getter=lambda res, args, kwargs: agent_name,
                user_id_getter=lambda res, args, kwargs: kwargs.get("user_id") or (res.get("user_id") if isinstance(res, dict) else None),
                request_id_getter=lambda res, args, kwargs: kwargs.get("request_id") or (res.get("request_id") if isinstance(res, dict) else None),
                provider_getter=lambda res, args, kwargs: "openai",
                operation_type="completion",
            )(orig_func)

            # Wrap decorated callable to inject user_id/request_id into the inputs (args[0] if dict) so
            # downstream tools and threads can read them from the payload even if ContextVar isn't propagated.
            try:
                import inspect
                def _make_injecting_wrapper(fn):
                    if inspect.iscoroutinefunction(fn):
                        async def _async_wrapper(*args, **kwargs):
                            # derive values from kwargs/args if present
                            try:
                                # If caller provided inputs via kwargs (common pattern: kickoff(inputs=...)),
                                # convert to the first positional dict arg when safe so decorated functions
                                # that expect kickoff(self, inputs_dict) receive it positionally.
                                kw_inputs = kwargs.get("inputs") or kwargs.get("input") or kwargs.get("payload")
                                if kw_inputs is not None and isinstance(kw_inputs, dict):
                                    # build new kwargs without the inputs key to avoid duplicate kw errors
                                    new_kwargs = dict(kwargs)
                                    new_kwargs.pop("inputs", None)
                                    new_kwargs.pop("input", None)
                                    new_kwargs.pop("payload", None)

                                    if args and len(args) > 0:
                                        # preserve self/instance as first arg and inject inputs as second
                                        new_args = (args[0], kw_inputs) + args[1:]
                                    else:
                                        # no instance present, place inputs as first arg
                                        new_args = (kw_inputs, ) + tuple(args[1:])

                                    kwargs_to_call = new_kwargs
                                else:
                                    # existing behavior: if first positional arg is a dict, merge user/request into it
                                    new_args = args
                                    kwargs_to_call = kwargs

                                if kw_inputs is None:
                                    # check positional dict input (common pattern: kickoff(self, inputs_dict))
                                    if args and len(args) > 0 and isinstance(args[0], dict):
                                        inputs = dict(args[0])
                                        if "user_id" not in inputs and "user_id" in kwargs:
                                            inputs["user_id"] = kwargs.get("user_id")
                                        if "request_id" not in inputs and "request_id" in kwargs:
                                            inputs["request_id"] = kwargs.get("request_id")
                                        # if still missing, try to read from request_context
                                        from utils.request_context import get_request_context
                                        ctx = get_request_context() or {}
                                        if "user_id" not in inputs and ctx.get("user_id"):
                                            inputs["user_id"] = ctx.get("user_id")
                                        if "request_id" not in inputs and ctx.get("request_id"):
                                            inputs["request_id"] = ctx.get("request_id")
                                        # replace first arg with modified dict
                                        new_args = (inputs, ) + args[1:]
                                    else:
                                        # no dict positional arg — do NOT inject arbitrary kwargs (avoids unexpected kw errors)
                                        # instead ensure request_context contains the values so nested/off-thread work
                                        new_args = args
                                        from utils.request_context import get_request_context, set_request_context
                                        ctx = get_request_context() or {}
                                        merged = dict(ctx)
                                        if "user_id" in kwargs and kwargs.get("user_id"):
                                            merged["user_id"] = kwargs.get("user_id")
                                        if "request_id" in kwargs and kwargs.get("request_id"):
                                            merged["request_id"] = kwargs.get("request_id")
                                        try:
                                            set_request_context(merged)
                                        except Exception:
                                            pass

                                return await fn(*new_args, **kwargs_to_call)
                            except Exception:
                                # best-effort: do not block the agent
                                return await fn(*args, **kwargs)
                        return _async_wrapper
                    else:
                        def _sync_wrapper(*args, **kwargs):
                            try:
                                kw_inputs = kwargs.get("inputs") or kwargs.get("input") or kwargs.get("payload")
                                if kw_inputs is not None and isinstance(kw_inputs, dict):
                                    new_kwargs = dict(kwargs)
                                    new_kwargs.pop("inputs", None)
                                    new_kwargs.pop("input", None)
                                    new_kwargs.pop("payload", None)

                                    if args and len(args) > 0:
                                        new_args = (args[0], kw_inputs) + args[1:]
                                    else:
                                        new_args = (kw_inputs, ) + tuple(args[1:])

                                    kwargs_to_call = new_kwargs
                                else:
                                    new_args = args
                                    kwargs_to_call = kwargs

                                if kw_inputs is None:
                                    if args and len(args) > 0 and isinstance(args[0], dict):
                                        inputs = dict(args[0])
                                        if "user_id" not in inputs and "user_id" in kwargs:
                                            inputs["user_id"] = kwargs.get("user_id")
                                        if "request_id" not in inputs and "request_id" in kwargs:
                                            inputs["request_id"] = kwargs.get("request_id")
                                        from utils.request_context import get_request_context
                                        ctx = get_request_context() or {}
                                        if "user_id" not in inputs and ctx.get("user_id"):
                                            inputs["user_id"] = ctx.get("user_id")
                                        if "request_id" not in inputs and ctx.get("request_id"):
                                            inputs["request_id"] = ctx.get("request_id")
                                        new_args = (inputs, ) + args[1:]
                                    else:
                                        new_args = args
                                        from utils.request_context import get_request_context, set_request_context
                                        ctx = get_request_context() or {}
                                        merged = dict(ctx)
                                        if "user_id" in kwargs and kwargs.get("user_id"):
                                            merged["user_id"] = kwargs.get("user_id")
                                        if "request_id" in kwargs and kwargs.get("request_id"):
                                            merged["request_id"] = kwargs.get("request_id")
                                        try:
                                            set_request_context(merged)
                                        except Exception:
                                            pass

                                return fn(*new_args, **kwargs_to_call)
                            except Exception:
                                return fn(*args, **kwargs)
                        return _sync_wrapper

                injecting_callable = _make_injecting_wrapper(decorated)
            except Exception as e:
                logger.exception("Failed to create injecting wrapper: %s", e)
                injecting_callable = decorated

            # Try instance-level assignment first (works for regular objects)
            try:
                setattr(crew, target_name, injecting_callable)
                CrewFactory._wrapped_instances.add(id(crew))
                return crew
            except Exception:
                print('Failed to set injecting wrapper on crew instance, trying class-level patch')
                # Some Crew implementations (pydantic models, frozen objects) disallow instance attribute assignment.
                # Fall back to patching the class so method binding works for existing and future instances.
                try:
                    setattr(type(crew), target_name, injecting_callable)
                    CrewFactory._wrapped_instances.add(id(crew))
                    logger.info("Patched %s.%s at class level for instrumentation", type(crew).__name__, target_name)
                    return crew
                except Exception as e:
                    logger.exception("Failed to set decorated method on class %s: %s", type(crew).__name__, e)
                    return crew

        except Exception as e:
            logger.exception("Failed to wrap Crew.%s: %s", target_name, e)
            return

    @classmethod
    def get_market_research_crew(cls) -> Crew:
        effective_prompt_id = cls._get_effective_prompt_id('market_research')
        print(f'Effective prompt ID for market_research: {effective_prompt_id}')
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
        print(f'Effective prompt ID for financial_advisor: {effective_prompt_id}')
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
        print(f'Effective prompt ID for product_strategist: {effective_prompt_id}')
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
        print(f'Effective prompt ID for summary_agent: {effective_prompt_id}')
        key = f"summary:{effective_prompt_id or 'latest'}"
        if key not in cls._crews:
            agent = AgentFactory.get_summary_agent(effective_prompt_id)
            task = create_summary_task(agent)
            cls._crews[key] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._wrap_crew_kickoff(cls._crews[key], graph_node_id="summary_node", agent_name="Summary Agent")
