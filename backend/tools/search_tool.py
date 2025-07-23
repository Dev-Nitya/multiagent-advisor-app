from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from langchain_community.tools.tavily_search import TavilySearchResults

class SearchInput(BaseModel):
    """Input schema for SearchTool."""
    query: str = Field(..., description="Search query to find information")

class SearchTool(BaseTool):
    name: str = "Search Tool"
    description: str = "A tool for searching information on the web"
    args_schema: Type[BaseModel] = SearchInput
    
    def _run(self, query: str) -> str:
        try:
            # Try to use Tavily if available
            tavily_tool = TavilySearchResults()
            results = tavily_tool.run(query)
            return str(results)
        except Exception as e:
            # Fallback to placeholder if Tavily is not working
            return f"Search results for '{query}': This is a placeholder search result. To get real search results, please ensure TAVILY_API_KEY is properly configured. Error: {str(e)}"

def get_search_tool():
    return SearchTool()