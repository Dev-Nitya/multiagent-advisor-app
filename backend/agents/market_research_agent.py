from crewai import Agent, Task, Crew
from langchain_core.language_models import BaseLLM
from typing import Optional

from agents.tasks.market_research_task import create_market_research_task

def create_market_research_agent(llm: Optional[BaseLLM] = None):
    agent_config = {
        "role": "Market Research Agent",
        "goal": "Analyze market trends, customer demands and competition for startup idea",
        "backstory": "You are an experienced market analyst known for identifying niche opportunities.",
        "allow_delegation": False,
        "verbose": False,
        "max_iter": 1,
        "output_json": {
            "summary": "Brief overview of market size, trends, and competition (1-2 sentences).",
            "verdict": "viable / not viable / uncertain",
            "viability_score": "A number between 0 (not viable) and 10 (very viable)"
        }
    }
    
    if llm:
        agent_config["llm"] = llm
    
    return Agent(**agent_config)

def create_market_crew():
    agent = create_market_research_agent()
    task = create_market_research_task(agent)

    return Crew(
        agents=[agent],
        tasks=[task]
    )