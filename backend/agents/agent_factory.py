from typing import Dict
from crewai import Agent

from backend.agents.market_research_agent import create_market_research_agent
from backend.agents.financial_advisor_agent import create_financial_advisor_agent
from backend.agents.product_strategist_agent import create_product_strategist_agent
from backend.agents.summary_agent import create_summary_agent
from backend.utils.llm_manager import LLMManager

class AgentFactory:
    _agents: Dict[str, Agent] = {}

    @classmethod
    def get_market_research_agent(cls) -> Agent:
        if "market_research" not in cls._agents:
            llm = LLMManager.get_fast_llm()  # Use fast LLM for market research
            cls._agents["market_research"] = create_market_research_agent(llm)
        return cls._agents["market_research"]
    
    @classmethod
    def get_financial_advisor_agent(cls) -> Agent:
        if "financial_advisor" not in cls._agents:
            llm = LLMManager.get_smart_llm()  # Use smart LLM for financial analysis
            cls._agents["financial_advisor"] = create_financial_advisor_agent(llm)
        return cls._agents["financial_advisor"]
    
    @classmethod
    def get_product_strategist_agent(cls) -> Agent:
        if "product_strategist" not in cls._agents:
            llm = LLMManager.get_default_llm()  # Use default LLM for product strategy
            cls._agents["product_strategist"] = create_product_strategist_agent(llm)
        return cls._agents["product_strategist"]
    
    @classmethod
    def get_summary_agent(cls) -> Agent:
        if "summary" not in cls._agents:
            llm = LLMManager.get_smart_llm()  # Use smart LLM for final summary
            cls._agents["summary"] = create_summary_agent(llm)
        return cls._agents["summary"]
    
    @classmethod
    def get_pool_stats(cls) -> dict:
        """Get connection pool statistics for monitoring"""
        return {
            "cached_agents": len(cls._agents),
            "llm_pool_stats": LLMManager.get_pool_stats()
        }