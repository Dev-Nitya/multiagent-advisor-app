from crewai import Task

from agents.tools.tool_factory import ToolFactory

def create_financial_advisor_task(agent):
    return Task(
        description=("""Using the market research findings, estimate the financial viability of building this idea {{idea}}.
                     Include estimated costs, potential pricing models, revenue potential, and profitability timeline."""),
        expected_output="""Financial feasibility report including cost breakdown, pricing strategy, and ROI estimate.
                            Return a json object with the following keys: 
                            "summary": "Summary of cost, revenue model, and ROI potential (2-3 sentences).",
                            "verdict": "viable / not viable / uncertain",
                            "viability_score": "A number between 0 and 10 based on financial feasibility"
        """,
        agent=agent,
        input_keys=["idea","market_insights","user_id","request_id"],
        tools=[ToolFactory.get_calculator_tool()]
    )