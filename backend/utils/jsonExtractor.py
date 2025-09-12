import json
import re
from typing import Any, Dict, Optional


def extract_json_from_raw(raw_text: str) -> Optional[Dict[str, Any]]:
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