from typing import Dict
from crewai import Crew

from backend.agents.agent_factory import AgentFactory
from backend.tasks.financial_advisor_task import create_financial_advisor_task
from backend.tasks.product_strategy_task import create_product_strategy_task
from backend.tasks.summary_task import create_summary_task
from backend.tasks.market_research_task import create_market_research_task

class CrewFactory:
    _crews: Dict[str, Crew] = {}

    @classmethod
    def get_market_research_crew(cls) -> Crew:
        if "market_research" not in cls._crews:
            agent = AgentFactory.get_market_research_agent()
            task = create_market_research_task(agent)
            cls._crews["market_research"] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._crews["market_research"]

    @classmethod
    def get_financial_analysis_crew(cls) -> Crew:
        if "financial_analysis" not in cls._crews:
            agent = AgentFactory.get_financial_advisor_agent()
            task = create_financial_advisor_task(agent)
            cls._crews["financial_analysis"] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._crews["financial_analysis"]
    
    @classmethod
    def get_product_strategy_crew(cls) -> Crew:
        if "product_strategy" not in cls._crews:
            agent = AgentFactory.get_product_strategist_agent()
            task = create_product_strategy_task(agent)
            cls._crews["product_strategy"] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._crews["product_strategy"]
    
    @classmethod
    def get_summary_crew(cls) -> Crew:
        if "summary" not in cls._crews:
            agent = AgentFactory.get_summary_agent()
            task = create_summary_task(agent)
            cls._crews["summary"] = Crew(
                agents=[agent],
                tasks=[task]
            )
        return cls._crews["summary"]