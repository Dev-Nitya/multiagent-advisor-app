from crewai import Agent, Task, Crew
from langchain_core.language_models import BaseLLM
from typing import Optional

from agents.tasks.summary_task import create_summary_task

def create_summary_agent(llm: Optional[BaseLLM] = None):
    agent_config = {
        "role": "Startup Advisor",
        "goal": "Review all agent outputs and deliver a final verdict with reasoning",
        "backstory": (
            "You are a senior startup advisor with experience in evaluating startup viability across markets, "
            "finance, and product design. Your job is to synthesize expert inputs and provide clear, actionable guidance."
        ),
        "allow_delegation": False,
        "verbose": True,
        "max_iter": 1,
        "output_json": {
            "market_verdict": "Copy of verdict from market analysis",
            "financial_verdict": "Copy of verdict from financial analysis",
            "product_verdict": "Copy of verdict from product analysis",
            "final_recommendation": "launch / iterate / abandon",
            "rationale": "Brief reasoning combining all inputs (2-3 sentences)",
            "confidence_score": "0–10 score reflecting how confident the advisor is in the final recommendation"
        }
    }
    
    if llm:
        agent_config["llm"] = llm
    
    return Agent(**agent_config)

def create_summary_crew():
    agent = create_summary_agent()
    task = create_summary_task(agent)
    
    return Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )