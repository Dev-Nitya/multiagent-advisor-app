from crewai import Agent, Task, Crew

from backend.tasks.market_research_task import create_market_research_task

def create_market_research_agent():
    return Agent(
        role="Market Research Agent",
        goal="Analyze market trends, customer demands and competition for startup idea",
        backstory="You are an experienced market analyst known for identifying niche opportunities.",
        allow_delegation=False,
        verbose=False,
        max_iter=1,
        output_json={
            "summary": "Brief overview of market size, trends, and competition (2-3 sentences).",
            "verdict": "viable / not viable / uncertain",
            "viability_score": "A number between 0 (not viable) and 10 (very viable)"
        }
    )

def create_market_crew():
    agent = create_market_research_agent()
    task = create_market_research_task(agent)

    return Crew(
        agents=[agent],
        tasks=[task]
    )