from typing import Any, Dict, Optional
from crewai import Agent

from agents.market_research_agent import create_market_research_agent
from agents.financial_advisor_agent import create_financial_advisor_agent
from agents.product_strategist_agent import create_product_strategist_agent
from agents.summary_agent import create_summary_agent
from utils.request_context import get_request_context
from utils.llm_manager import LLMManager
from services.prompt_registry import prompt_registry

class AgentFactory:
    _agents: Dict[str, Agent] = {}

    def _get_llm_by_prompt_settings(prompt_id: Optional[str]) -> Any:
        # Prefer explicit prompt_id argument, fall back to request-context prompt_id when available
        effective_prompt_id = prompt_id
        if not effective_prompt_id:
            try:
                ctx = get_request_context() or {}
                effective_prompt_id = ctx.get("prompt_id")
            except Exception:
                effective_prompt_id = None

        # If we have an effective prompt id, try to load its settings and build an LLM from them
        if effective_prompt_id:
            prompt = prompt_registry.get_prompt_by_id(effective_prompt_id)
            if prompt:
                # prompt may be a dict or an ORM object; handle both
                try:
                    model_settings = prompt.get("model_settings") if isinstance(prompt, dict) else getattr(prompt, "model_settings", None)
                except Exception:
                    model_settings = None

                if isinstance(model_settings, str):
                    try:
                        import json
                        model_settings = json.loads(model_settings)
                    except Exception:
                        pass

                if model_settings:
                    llm = LLMManager.get_llm_from_settings(model_settings)
                    try:
                        setattr(llm, "prompt_id", effective_prompt_id)
                    except Exception:
                        pass
                    return llm

        # fallback to default LLM
        return LLMManager.get_default_llm()

    @classmethod
    def get_market_research_agent(cls, prompt_id: Optional[str] = None) -> Agent:
        key = f"market_research:{prompt_id or 'latest'}"
        if key not in cls._agents:
            llm = cls._get_llm_by_prompt_settings(prompt_id)
            cls._agents["market_research"] = create_market_research_agent(llm)
        return cls._agents["market_research"]
    
    @classmethod
    def get_financial_advisor_agent(cls, prompt_id: Optional[str] = None) -> Agent:
        key = f"financial_advisor:{prompt_id or 'latest'}"
        if key not in cls._agents:
            llm = cls._get_llm_by_prompt_settings(prompt_id)
            cls._agents[key] = create_financial_advisor_agent(llm)
        return cls._agents[key]
    
    @classmethod
    def get_product_strategist_agent(cls, prompt_id: Optional[str] = None) -> Agent:
        key = f"product_strategist:{prompt_id or 'latest'}"
        if key not in cls._agents:
            llm = cls._get_llm_by_prompt_settings(prompt_id)
            cls._agents[key] = create_product_strategist_agent(llm)
        return cls._agents[key]
    
    @classmethod
    def get_summary_agent(cls, prompt_id: Optional[str] = None) -> Agent:
        key = f"summary:{prompt_id or 'latest'}"
        if key not in cls._agents:
            llm = cls._get_llm_by_prompt_settings(prompt_id)
            cls._agents[key] = create_summary_agent(llm)
        return cls._agents[key]
    
    @classmethod
    def get_pool_stats(cls) -> dict:
        """Get connection pool statistics for monitoring"""
        return {
            "cached_agents": len(cls._agents),
            "llm_pool_stats": LLMManager.get_pool_stats()
        }