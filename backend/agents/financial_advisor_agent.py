from crewai import Agent, Task, Crew
from langchain_core.language_models import BaseLLM
from typing import Optional

from agents.tasks.financial_advisor_task import create_financial_advisor_task

def create_financial_advisor_agent(llm: Optional[BaseLLM] = None):
    agent_config = {
        "role": "Financial Advisor",
        "goal": "Estimate cost, ROI, pricing models, and profit potential",
        "backstory": (
             """You are a sharp financial consultant who helps founders understand whether a startup
             is financially viable based on market analysis and revenue models."""
        ),
        "allow_delegation": False,
        "verbose": False,
        "max_iter": 1,
        "output_json": {
            "summary": "Summary of cost, revenue model, and ROI potential (1-2 sentences).",
            "verdict": "viable / not viable / uncertain",
            "viability_score": "A number between 0 and 10 based on financial feasibility"
        }
    }
    
    if llm:
        agent_config["llm"] = llm
    
    return Agent(**agent_config)

def create_finance_crew():
    agent = create_financial_advisor_agent()
    task = create_financial_advisor_task(agent)
    return Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )