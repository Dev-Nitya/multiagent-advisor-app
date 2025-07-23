from crewai import Task

from backend.tools.tool_factory import ToolFactory

def create_market_research_task(agent):
    return Task(
        description=f"""
        Based on your knowledge (no external search needed), quickly assess:
        - Market demand for: {'{idea}'}
        - Competition level
        - Business viability
        """,
        expected_output="""Return a json object with the following keys:
        "summary": "Brief overview of market size, trends, and competition (2-3 sentences).",
        "verdict": "viable / not viable / uncertain",
        "viability_score": "A number between 0 (not viable) and 10 (very viable)"
        """,
        agent=agent,
        tools=[ToolFactory.get_search_tool()],
    )