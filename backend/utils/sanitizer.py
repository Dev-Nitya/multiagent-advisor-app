import json

def sanitize_agent_output(output):
    # If it's a CrewOutput-like dict with a "raw" string inside
    if isinstance(output, dict) and "raw" in output:
        try:
            return json.loads(output["raw"])
        except json.JSONDecodeError:
            return {"raw": output["raw"]}
    
    # If it's nested in "tasks_output"
    if isinstance(output, dict) and "tasks_output" in output:
        raw_data = output["tasks_output"][0].get("raw")
        if raw_data:
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError:
                return {"raw": raw_data}
    
    # If it's just a stringified JSON
    if isinstance(output, str):
        try:
            return json.loads(output)
        except:
            return {"response": output}

    # Already a dict
    if isinstance(output, dict):
        return output

    # If it's a Pydantic object or something else
    if hasattr(output, "dict"):
        return output.dict()

    return {"response": str(output)}
