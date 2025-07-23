from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

from backend.crews.crew_factory import CrewFactory
from backend.utils.sanitizer import sanitize_agent_output

class AgentState(TypedDict):
    idea: str
    market_analysis: Annotated[str, "market_output"]
    financial_analysis: Annotated[str, "financial_output"]
    product_strategy: Annotated[str, "product_output"]
    final_summary: Annotated[str, "summary_output"]
    market_retries: int

def market_node(state: AgentState) -> AgentState:
    idea = state["idea"]
    retries = state.get("market_retries", 0)
    print(f"🧠 Running market analysis on: {idea}")

    result = CrewFactory.get_market_research_crew().kickoff(inputs={"idea": idea})
    sanitized_result = sanitize_agent_output(result)

    print(f"Market analysis result: {sanitized_result}")
    return {**state, "market_analysis": sanitized_result, "market_retries": retries + 1}

def finance_node(state: AgentState) -> AgentState:
    market_insights = state["market_analysis"]
    idea = state["idea"]
    print(f"💰 Running financial analysis based on market insights: {market_insights}")

    result = CrewFactory.get_financial_analysis_crew().kickoff(inputs={"market_insights": market_insights, "idea": idea})
    sanitized_result = sanitize_agent_output(result)
    return {**state, "financial_analysis": sanitized_result}

def product_node(state: AgentState) -> AgentState:
    idea = state["idea"]
    financial_insights = state["financial_analysis"]
    print(f"📦 Developing product strategy based on financial insights: {financial_insights}")

    result = CrewFactory.get_product_strategy_crew().kickoff(inputs={"financial_insights": financial_insights, "idea": idea})
    sanitized_result = sanitize_agent_output(result)
    return {**state, "product_strategy": sanitized_result}

def summary_node(state: AgentState) -> AgentState:
    print(f"📝 Summarizing final output")
    result = CrewFactory.get_summary_crew().kickoff(inputs={
        "market_analysis": state["market_analysis"],
        "financial_analysis": state["financial_analysis"],
        "product_strategy": state["product_strategy"]
    })
    sanitized_result = sanitize_agent_output(result)
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