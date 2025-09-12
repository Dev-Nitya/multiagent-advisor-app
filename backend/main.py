from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.redis_cache import cache
from config.settings import settings
from config.database import get_db, db_manager
from api.evaluate_startup import startup_router
from api.prompt import prompt_router
from api.cost import cost_router
from api.admin.prompt_config import admin_router
from api.auth import router as auth_router
from agents.agent_factory import AgentFactory
from agents.tools.tool_factory import ToolFactory
from utils.llm_manager import LLMManager
from middleware.rate_limit_middleware import RateLimitMiddleware
from middleware.cost_monitoring_middleware import CostMonitoringMiddleware
from config.logging import configure_logging
from middleware.correlation_id import CorrelationIdMiddleware
# from scripts.add_created_at import seed_model_pricing

load_dotenv()

app = FastAPI(
    title="Multi-Agent Startup Advisor",
    description="AI-powered startup idea evaluation using multiple specialized agents",
    version="1.0.0"
)

configure_logging()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    skip_paths=["/docs", "/redoc", "/openapi.json", "/health/live"]
)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CostMonitoringMiddleware
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
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(prompt_router)
app.include_router(cost_router)

@app.get("/health/pool-stats")
async def get_pool_stats():
    """Get connection pool statistics for monitoring"""
    return AgentFactory.get_pool_stats()

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "multi-agent-advisor"}
