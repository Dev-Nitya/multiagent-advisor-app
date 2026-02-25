from crewai import Task

def create_product_strategy_task(agent):
    return Task(
    description=(
        """Based on financial analysis, design a product strategy for the app idea {{idea}}. 
        Identify must-have features, target user personas, MVP scope, and GTM (go-to-market) strategy."""
    ),
    expected_output="""
        Return a JSON object with:
        {
          "summary": "Brief evaluation of product uniqueness, technical feasibility, and UX potential",
          "verdict": "viable | not viable | uncertain",
          "viability_score": "Number 0-10 based on product strength",
          "product_strategy": {
            "user_personas": [
              {"name": "string", "description": "string"}
            ],
            "must_have_features": ["string"],
            "MVP_scope": "string",
            "GTM_strategy": "string"
          }
        }
    """,
    agent=agent,
    input_keys=["idea", "financial_insights", "user_id", "request_id"],
)
