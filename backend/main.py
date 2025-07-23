from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.api.evaluate_startup import startup_router
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

app.include_router(startup_router)
