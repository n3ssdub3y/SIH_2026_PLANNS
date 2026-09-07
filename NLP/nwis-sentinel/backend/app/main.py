"""
NWIS-Sentinel: FastAPI Backend (P4's core module)
Main application entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import wells, events, matching, telemetry

app = FastAPI(
    title="NWIS-Sentinel API",
    description="Nearby Wells Intelligence System — AI-powered drilling knowledge retrieval",
    version="0.1.0"
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(wells.router, prefix="/api/wells", tags=["Wells"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(matching.router, prefix="/api/matching", tags=["Matching"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["Telemetry"])


@app.get("/")
def root():
    return {
        "name": "NWIS-Sentinel",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "wells": "/api/wells",
            "events": "/api/events",
            "matching": "/api/matching/analogs",
            "telemetry": "/api/telemetry/stream",
            "docs": "/docs"
        }
    }
