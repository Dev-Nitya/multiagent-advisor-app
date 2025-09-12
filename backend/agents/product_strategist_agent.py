from crewai import Agent, Task, Crew
from langchain_core.language_models import BaseLLM
from typing import Optional

from agents.tasks.product_strategy_task import create_product_strategy_task

def create_product_strategist_agent(llm: Optional[BaseLLM] = None):
    agent_config = {
        "role": "Product Strategist",
        "goal": "Quickly assess product viability and key features. Only give 3 features",
        "backstory": (
            """You're an experienced product strategist focused on rapid MVP validation."""
        ),
        "allow_delegation": False,
        "verbose": False,
        "max_iter": 1,
        "max_execution_time": 15,
        "output_json": {
            "summary": "Evaluation of product uniqueness, technical feasibility, and UX potential (1-2 sentences).",
            "verdict": "viable / not viable / uncertain",
            "viability_score": "A number between 0 and 10 based on product strength"
        }
    }
    
    if llm:
        agent_config["llm"] = llm
    
    return Agent(**agent_config)

def create_product_strategy_crew():
    agent = create_product_strategist_agent()
    task = create_product_strategy_task(agent)
    
    return Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )