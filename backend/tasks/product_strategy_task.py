from crewai import Task

def create_product_strategy_task(agent):
    return Task(
        description=("""Based on financial analysis, design a product strategy for an app for this idea {{idea}}. 
                     Identify must-have features, target user personas, MVP scope, and GTM (go-to-market) strategy."""),
        expected_output="""Product strategy report with user personas, feature set, and launch plan.
            Return a json object with the following keys:
            "summary": "Evaluation of product uniqueness, technical feasibility, and UX potential.",
            "verdict": "viable / not viable / uncertain",
            "viability_score": "A number between 0 and 10 based on product strength"
        """,
        agent=agent,
        input_keys=["idea","financial_insights"]
    )