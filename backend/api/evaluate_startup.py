from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import re

from backend.langgraph.advisor_graph import build_graph

startup_router = APIRouter()

class StartupIdeaRequest(BaseModel):
    idea: str

def extract_json_from_raw(raw_text):
    """Extract JSON from raw text that might contain markdown code blocks"""
    if not raw_text:
        return None
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to parse the entire text as JSON
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    
    return None

def process_final_summary(final_summary):
    """Process the final summary to extract structured data"""
    if not final_summary or not isinstance(final_summary, dict):
        return None
    
    # Get the raw content from tasks_output
    tasks_output = final_summary.get('tasks_output', [])
    if not tasks_output:
        return None
    
    raw_content = tasks_output[0].get('raw', '')
    
    # Extract JSON from the raw content
    extracted_data = extract_json_from_raw(raw_content)
    
    if extracted_data:
        return {
            "market_verdict": extracted_data.get("market_verdict", ""),
            "financial_verdict": extracted_data.get("financial_verdict", ""),
            "product_verdict": extracted_data.get("product_verdict", ""),
            "final_recommendation": extracted_data.get("final_recommendation", ""),
            "rationale": extracted_data.get("rationale", ""),
            "confidence_score": extracted_data.get("confidence_score", 0)
        }
    
    # Fallback to raw text if JSON extraction fails
    return {
        "summary": raw_content,
        "final_recommendation": "uncertain",
        "confidence_score": 0
    }

@startup_router.post("/evaluate")
async def evaluate_startup(request: StartupIdeaRequest):
    try:
        graph = build_graph()
        result = graph.invoke({"idea": request.idea})
        
        # Extract and process only the final summary
        final_summary = result.get("final_summary")
        processed_summary = process_final_summary(final_summary)
        
        if not processed_summary:
            raise HTTPException(status_code=500, detail="Failed to process final summary")
        
        return processed_summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))