from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class CalculatorInput(BaseModel):
    """Input schema for CalculatorTool."""
    expression: str = Field(..., description="Mathematical expression to evaluate")

class CalculatorTool(BaseTool):
    name: str = "Calculator"
    description: str = "A simple calculator tool for mathematical calculations"
    args_schema: Type[BaseModel] = CalculatorInput
    
    def _run(self, expression: str) -> str:
        try:
            # Use eval safely for basic mathematical expressions
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"Error evaluating expression '{expression}': {e}"

def get_calculator_tool():
    return CalculatorTool()
