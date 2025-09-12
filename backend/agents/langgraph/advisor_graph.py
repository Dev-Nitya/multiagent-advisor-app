from langgraph.graph import StateGraph, END
from typing import Optional, TypedDict, Annotated

from agents.crews.crew_factory import CrewFactory
from utils.sanitizer import sanitize_agent_output
from utils.request_context import get_request_context
from services.cost_service import BudgetExceeded

class AgentState(TypedDict):
    idea: str
    market_analysis: Annotated[str, "market_output"]
    financial_analysis: Annotated[str, "financial_output"]
    product_strategy: Annotated[str, "product_output"]
    final_summary: Annotated[str, "summary_output"]
    market_retries: int
    # optional request context forwarded into the graph state
    user_id: Optional[str]
    request_id: Optional[str]

def market_node(state: AgentState) -> AgentState:
    idea = state["idea"]
    request_id = state["request_id"]
    user_id = state["user_id"]
    retries = state.get("market_retries", 0)

    ctx = get_request_context() or {}
    prev_node = ctx.get("graph_node_id")
    prev_agent = ctx.get("agent_id")
    ctx["graph_node_id"] = "market_node"
    ctx["agent_id"] = "Market Research Agent"

    try:
        result = CrewFactory.get_market_research_crew().kickoff(inputs={"idea": idea, "user_id": user_id, "request_id": request_id})
    except BudgetExceeded:
        # propagate so upper layer (evaluate_startup) can return a budget-exceeded response
        raise
    finally:
        # restore context
        if prev_node is None:
            ctx.pop("graph_node_id", None)
        else:
            ctx["graph_node_id"] = prev_node
        if prev_agent is None:
            ctx.pop("agent_id", None)
        else:
            ctx["agent_id"] = prev_agent

    sanitized_result = sanitize_agent_output(result)
    print(f'Market analysis result {sanitized_result}')  # Debug print

    return {**state, "market_analysis": sanitized_result, "market_retries": retries + 1}

def finance_node(state: AgentState) -> AgentState:
    market_insights = state["market_analysis"]
    idea = state["idea"]
    user_id = state["user_id"]
    request_id = state["request_id"]

    ctx = get_request_context() or {}
    prev_node = ctx.get("graph_node_id")
    prev_agent = ctx.get("agent_id")
    ctx["graph_node_id"] = "finance_node"
    ctx["agent_id"] = "Financial Advisor"

    try:
        result = CrewFactory.get_financial_analysis_crew().kickoff(
            inputs={"market_insights": market_insights, 
                    "idea": idea, "user_id": user_id, 
                    "request_id": request_id})
    except BudgetExceeded:
        raise
    finally:
        if prev_node is None:
            ctx.pop("graph_node_id", None)
        else:
            ctx["graph_node_id"] = prev_node
        if prev_agent is None:
            ctx.pop("agent_id", None)
        else:
            ctx["agent_id"] = prev_agent

    sanitized_result = sanitize_agent_output(result)
    print(f'Financial analysis result {sanitized_result}')  # Debug print

    return {**state, "financial_analysis": sanitized_result}

def product_node(state: AgentState) -> AgentState:
    idea = state["idea"]
    financial_insights = state["financial_analysis"]
    user_id = state["user_id"]
    request_id = state["request_id"]

    ctx = get_request_context() or {}
    prev_node = ctx.get("graph_node_id")
    prev_agent = ctx.get("agent_id")
    ctx["graph_node_id"] = "product_node"
    ctx["agent_id"] = "Product Strategy Agent"

    try:
        result = CrewFactory.get_product_strategy_crew().kickoff(inputs={"financial_insights": financial_insights, "idea": idea, "user_id": user_id, "request_id": request_id})
    except BudgetExceeded:
        raise
    finally:
        if prev_node is None:
            ctx.pop("graph_node_id", None)
        else:
            ctx["graph_node_id"] = prev_node
        if prev_agent is None:
            ctx.pop("agent_id", None)
        else:
            ctx["agent_id"] = prev_agent

    sanitized_result = sanitize_agent_output(result)
    print(f'Product strategy result {sanitized_result}')  # Debug print

    return {**state, "product_strategy": sanitized_result}

def summary_node(state: AgentState) -> AgentState:
    user_id = state["user_id"]
    request_id = state["request_id"]

    ctx = get_request_context() or {}
    prev_node = ctx.get("graph_node_id")
    prev_agent = ctx.get("agent_id")
    ctx["graph_node_id"] = "summary_node"
    ctx["agent_id"] = "Summary Agent"

    try:
        result = CrewFactory.get_summary_crew().kickoff(inputs={
            "market_analysis": state["market_analysis"],
            "financial_analysis": state["financial_analysis"],
            "product_strategy": state["product_strategy"],
            "user_id": user_id,
            "request_id": request_id
        })
    except BudgetExceeded:
        raise
    finally:
        if prev_node is None:
            ctx.pop("graph_node_id", None)
        else:
            ctx["graph_node_id"] = prev_node
        if prev_agent is None:
            ctx.pop("agent_id", None)
        else:
            ctx["agent_id"] = prev_agent
            
    sanitized_result = sanitize_agent_output(result)

    print("Final summary result:", sanitized_result)  # Debug print
    
    return {**state, "final_summary": sanitized_result}

def check_market_viability(state: AgentState) -> str:
    try:
        if state["market_analysis"]["verdict"].lower() == "not viable" and state["market_retries"] < 3:
            return "market_node"
    except Exception as e:
        print(f"Error checking market viability: {e}, defaulting to market_node")

    return "finance_node"

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("market_node", market_node)
    graph.add_node("finance_node", finance_node)
    graph.add_node("product_node", product_node)
    graph.add_node("summary_node", summary_node)

    graph.set_entry_point("market_node")
    
    graph.add_conditional_edges("market_node", check_market_viability, {
        "market_node": "market_node",
        "finance_node": "finance_node"
    })

    graph.add_edge("finance_node", "product_node")
    graph.add_edge("product_node", "summary_node")
    graph.add_edge("summary_node", END)

    return graph.compile()