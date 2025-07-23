from typing import Dict
from crewai.tools import BaseTool

from backend.tools.search_tool import SearchTool
from backend.tools.calculator_tool import CalculatorTool

class ToolFactory:
    _tools: Dict[str, BaseTool] = {}

    @classmethod
    def get_search_tool(cls) -> SearchTool:
        if "search" not in cls._tools:
            cls._tools["search"] = SearchTool()
        return cls._tools["search"]
    
    @classmethod
    def get_calculator_tool(cls) -> CalculatorTool:
        if "calculator" not in cls._tools:
            cls._tools["calculator"] = CalculatorTool()
        return cls._tools["calculator"]