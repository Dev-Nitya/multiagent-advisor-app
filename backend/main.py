from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.api.evaluate_startup import startup_router
from backend.agents.agent_factory import AgentFactory
from backend.tools.tool_factory import ToolFactory
from backend.utils.llm_manager import LLMManager

load_dotenv()

app = FastAPI(
    title="Multi-Agent Startup Advisor",
    description="AI-powered startup idea evaluation using multiple specialized agents",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Pre-initialize agents and tools to reduce first-request latency"""
    print("🚀 Warming up agents and tools...")

    # Pre-warm LLM connections
    print("🔗 Initializing LLM connection pool...")
    LLMManager()  # Initialize singleton
    
    # Pre-initialize agents (this will create pooled LLM instances)
    AgentFactory.get_market_research_agent()
    AgentFactory.get_financial_advisor_agent()
    AgentFactory.get_product_strategist_agent()
    AgentFactory.get_summary_agent()

    # Pre-initialize tools
    ToolFactory.get_search_tool()
    ToolFactory.get_calculator_tool()

    print("✅ Agents and tools warmed up successfully!")
    print(f"📊 Pool stats: {AgentFactory.get_pool_stats()}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on app shutdown"""
    print("🔄 Closing LLM connections...")
    LLMManager.close_connections()
    print("✅ Cleanup completed!")


app.include_router(startup_router)

@app.get("/health/pool-stats")
async def get_pool_stats():
    """Get connection pool statistics for monitoring"""
    return AgentFactory.get_pool_stats()

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "multi-agent-advisor"}
