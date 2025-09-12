from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from langchain_community.tools.tavily_search import TavilySearchResults

# new imports
import logging
from utils.request_context import get_request_context
from services.cost_service import record_cost_event, BudgetExceeded

logger = logging.getLogger(__name__)

class SearchInput(BaseModel):
    """Input schema for SearchTool."""
    query: str = Field(..., description="Search query to find information")

class SearchTool(BaseTool):
    name: str = "Search Tool"
    description: str = "A tool for searching information on the web"
    args_schema: Type[BaseModel] = SearchInput
    
    def _run(self, query: str) -> str:
        ctx = get_request_context() or {}
        user_id = ctx.get("user_id")
        request_id = ctx.get("request_id")
        graph_node_id = ctx.get("graph_node_id") or "search_tool"
        agent_id = ctx.get("agent_id") or "Search Tool"
        tool_id = "tavily_search"
        prompt_id = ctx.get("prompt_id")

        try:
            # Try to use Tavily if available
            tavily_tool = TavilySearchResults()
            results = tavily_tool.run(query)

            # If the tool returns structured usage, persist it; otherwise record a retrieval event (best-effort)
            try:
                tu = results if isinstance(results, dict) else None
                if tu and (tu.get("token_usage") or tu.get("usage") or tu.get("tokens")):
                    # If nested token_usage exists, normalize
                    token_block = tu.get("token_usage") or tu.get("usage") or tu.get("tokens")
                    prompt = token_block.get("prompt_tokens")
                    completion = token_block.get("completion_tokens")
                    total = token_block.get("total_tokens")
                    cached = bool(token_block.get("cached_prompt_tokens", 0))

                    record_cost_event(
                        user_id=user_id,
                        request_id=request_id,
                        graph_node_id=graph_node_id,
                        agent_id=agent_id,
                        tool_id=tool_id,
                        provider="tavily",
                        model_name=token_block.get("model") or token_block.get("model_name"),
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        total_tokens=total,
                        operation_type="retrieval",
                        successful=True,
                        cached=cached,
                        note="tavily_provided_usage",
                        prompt_id=prompt_id
                    )
                else:
                    # No token info -> record retrieval with zero tokens (note for auditing)
                    record_token_usage_tool(
                        user_id=user_id, request_id=request_id, graph_node_id=graph_node_id,
                        agent_id=agent_id, tool_id=tool_id, note="external_search_no_token_info",
                        is_successful=True, prompt_id=prompt_id
                    )
            except BudgetExceeded:
                # enforce budget upstream by re-raising
                logger.warning("Budget exceeded while recording search_tool usage for user=%s", user_id)
                raise
            except Exception:
                logger.exception("Failed to record search_tool cost event (non-fatal)")

            return str(results)
        except Exception as e:
            # record a failed retrieval attempt (best-effort) and return fallback text
            try:
                record_token_usage_tool(
                    user_id=user_id, request_id=request_id, graph_node_id=graph_node_id,
                    agent_id=agent_id, tool_id=tool_id, note=f"search_error: {str(e)}", 
                    is_successful=False, prompt_id=prompt_id)
            except BudgetExceeded:
                logger.warning("Budget exceeded while recording failed search attempt for user=%s", user_id)
                raise
            except Exception:
                logger.exception("Failed to record failed search_tool event (non-fatal)")
            return f"Search results for '{query}': This is a placeholder search result. To get real search results, please ensure TAVILY_API_KEY is properly configured. Error: {str(e)}"

def get_search_tool():
    return SearchTool()

def record_token_usage_tool(
        user_id: str, 
        request_id: str, 
        graph_node_id: str, 
        agent_id: str, 
        tool_id: str, 
        note: str,
        is_successful: bool = False,
        prompt_id: str = None):
    record_cost_event(
        user_id=user_id,
        request_id=request_id,
        graph_node_id=graph_node_id,
        agent_id=agent_id,
        tool_id=tool_id,
        provider="tavily",
        model_name=None,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        operation_type="retrieval",
        successful=is_successful,
        cached=False,
        note=note,
        prompt_id=prompt_id
    )