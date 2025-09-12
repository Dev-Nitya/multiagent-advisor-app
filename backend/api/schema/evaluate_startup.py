from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

class AgentPrompt(BaseModel):
    market_research: Optional[str] = Field(None, description="Prompt ID for Market Research Agent")
    financial_advisor: Optional[str] = Field(None, description="Prompt ID for Financial Advisor Agent")
    product_strategist: Optional[str] = Field(None, description="Prompt ID for Product Strategist Agent")
    summary_agent: Optional[str] = Field(None, description="Prompt ID for Summary Agent")

class StartupIdeaRequest(BaseModel):
    idea: str = Field(..., description="Short description of the startup idea")
    user_id: str = Field("anonymous", description="User ID of the requester")
    request_id: Optional[str] = Field(None, description="Optional request ID for tracking")
    # Either global prompt_id for all agents, or per-agent mapping
    global_prompt_id: Optional[str] = Field(None, description="Optional prompt ID for tracking")
    agent_prompt_ids: Optional[AgentPrompt] = Field(
        None,
        description="Optional mapping of agent_key -> prompt_id to use different prompts per agent"
    )

class EvaluateSummary(BaseModel):
    """
    Canonical response model for /evaluate.
    Fields are optional to allow graceful fallback responses while keeping a strict schema.
    """
    summary: Optional[str] = Field(None, description="Raw text summary when structured JSON is not provided")
    market_verdict: Optional[str] = Field(None, description="Market verdict (e.g., viable / not viable / uncertain)")
    financial_verdict: Optional[str] = Field(None, description="Financial outlook / viability")
    product_verdict: Optional[str] = Field(None, description="Product / tech feasibility verdict")
    final_recommendation: Optional[str] = Field(None, description="Final recommendation (go / no-go / pivot / uncertain)")
    rationale: Optional[str] = Field(None, description="Rationale supporting the recommendation")
    confidence_score: float = Field(0.0, ge=0.0, description="Confidence score (numeric, 0.0 or higher)")
    request_id: Optional[str] = Field(None, description="Echoed request ID for tracking")

# Example request body
EVALUATE_REQUEST_EXAMPLE: Dict[str, Any] = {
    "idea": "A mobile app that helps remote teams schedule meetings across time zones with intelligent suggestions.",
    "user_id": "user_123",
    "request_id": "req-abc-001",
    "agent_prompt_ids": {
        "market_research": "prompt-market-v2",
        "financial_analysis": "prompt-finance-v1",
        "product_strategist": "prompt-product-v3",
        "summary_agent": "prompt-summary-v1"
    }
}

# Successful structured response
EVALUATE_RESPONSE_EXAMPLE: Dict[str, Any] = {
    "summary": None,
    "market_verdict": "viable",
    "financial_verdict": "break-even within 18 months with freemium + enterprise",
    "product_verdict": "feasible with existing calendar APIs; moderate engineering effort",
    "final_recommendation": "go",
    "rationale": "Large addressable market in remote-first companies; low integration barriers; clear monetization paths.",
    "confidence_score": 0.78
}

EVALUATE_FALLBACK_RESPONSE: Dict[str, Any] = {
    "summary": "LLM returned an unstructured summary: The idea has promise but needs more market validation.",
    "market_verdict": None,
    "financial_verdict": None,
    "product_verdict": None,
    "final_recommendation": "uncertain",
    "rationale": None,
    "confidence_score": 0.0
}

# Error response example
EVALUATE_ERROR_RESPONSE: Dict[str, Any] = {
    "detail": "Failed to process final summary"
}

def get_evaluate_openapi_responses() -> Dict[int, Dict[str, Any]]:
    """
    Returns a mapping suitable for the FastAPI `responses=` parameter on the route.
    Each entry includes a minimal description and an example under application/json.
    """
    return {
        200: {
            "description": "Successful evaluation (structured when available, otherwise fallback summary).",
            "content": {
                "application/json": {
                    "example": EVALUATE_RESPONSE_EXAMPLE
                }
            }
        },
        202: {
            "description": "Accepted — evaluation is queued/processing (if you implement async/queued runs).",
            "content": {
                "application/json": {
                    "example": {"detail": "Evaluation accepted; processing in background", "request_id": "req-abc-001"}
                }
            }
        },
        500: {
            "description": "Internal server error or processing failure.",
            "content": {
                "application/json": {
                    "example": EVALUATE_ERROR_RESPONSE
                }
            }
        }
    }