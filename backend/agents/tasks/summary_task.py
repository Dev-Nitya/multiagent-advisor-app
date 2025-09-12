from crewai import Task

def create_summary_task(agent):
    return Task(
        description=("""Summarize the market research, financial analysis, and product strategy into a single advisory report.
                     Give a final recommendation on whether or not to build this startup and why."""),
        expected_output="""A 3-part structured markdown summary + final recommendation (yes/no with reason).
            Return a json object with the following keys:
            "market_verdict": "Copy of verdict from market analysis",
            "financial_verdict": "Copy of verdict from financial analysis",
            "product_verdict": "Copy of verdict from product analysis",
            "final_recommendation": "launch / iterate / abandon",
            "rationale": "Brief reasoning combining all inputs (3–5 sentences)",
            "confidence_score": "0–10 score reflecting how confident the advisor is in the final recommendation"
            """,
        agent=agent,
        input_keys=["market_analysis", "financial_analysis", "product_strategy", "user_id", "request_id"]
    )
