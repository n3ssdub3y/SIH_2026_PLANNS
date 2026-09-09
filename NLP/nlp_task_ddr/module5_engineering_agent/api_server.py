"""
api_server.py — FastAPI server for Module 5 Engineering Agent
Provides REST API endpoints for agent querying.
"""
import sys
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure module5 directory is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api.routes import router
from config import API_HOST, API_PORT
import uvicorn

app = FastAPI(
    title="Module 5: Engineering RAG + LLM Agent",
    description="Evidence-grounded drilling engineering decision support agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "healthy", "service": "module5_engineering_agent"}

if __name__ == "__main__":
    uvicorn.run("api_server:app", host=API_HOST, port=API_PORT, reload=False)
