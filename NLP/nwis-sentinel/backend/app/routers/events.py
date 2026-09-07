"""Events router — CRUD for drilling events."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data.demo_data import DEMO_EVENTS

router = APIRouter()

# In-memory event store (seeded with demo data)
_events_db = list(DEMO_EVENTS)


@router.get("/")
def list_events(
    well_id: Optional[str] = None,
    event_type: Optional[str] = None,
    min_depth: Optional[float] = None,
    max_depth: Optional[float] = None,
    formation: Optional[str] = None,
    severity: Optional[str] = None
):
    """List events with optional filters."""
    results = _events_db
    
    if well_id:
        results = [e for e in results if e["well_id"] == well_id]
    if event_type:
        results = [e for e in results if e["event_type"] == event_type]
    if formation:
        results = [e for e in results if e.get("formation", "").lower() == formation.lower()]
    if severity:
        results = [e for e in results if e.get("severity") == severity]
    if min_depth is not None:
        results = [e for e in results if e.get("depth_start_m", 0) >= min_depth]
    if max_depth is not None:
        results = [e for e in results if e.get("depth_start_m", float("inf")) <= max_depth]
    
    return {"events": results, "count": len(results)}


@router.get("/summary")
def event_summary():
    """Summary statistics of all events in the database."""
    by_type = {}
    by_well = {}
    by_formation = {}
    
    for e in _events_db:
        by_type[e["event_type"]] = by_type.get(e["event_type"], 0) + 1
        by_well[e["well_id"]] = by_well.get(e["well_id"], 0) + 1
        fm = e.get("formation", "Unknown")
        by_formation[fm] = by_formation.get(fm, 0) + 1
    
    return {
        "total_events": len(_events_db),
        "by_type": by_type,
        "by_well": by_well,
        "by_formation": by_formation
    }


@router.get("/{event_id}")
def get_event(event_id: str):
    """Get a single event by ID."""
    for e in _events_db:
        if e["event_id"] == event_id:
            return e
    raise HTTPException(status_code=404, detail=f"Event {event_id} not found")


@router.post("/")
def create_event(event: dict):
    """Add a new event (from NLP extraction or manual entry)."""
    # Auto-assign event ID
    max_id = max((int(e["event_id"].split("-")[1]) for e in _events_db), default=0)
    event["event_id"] = f"EVT-{max_id + 1:04d}"
    _events_db.append(event)
    return {"status": "created", "event": event}


@router.post("/batch")
def create_events_batch(events: list[dict]):
    """Add multiple events at once (from batch NLP extraction)."""
    max_id = max((int(e["event_id"].split("-")[1]) for e in _events_db), default=0)
    for i, event in enumerate(events):
        event["event_id"] = f"EVT-{max_id + 1 + i:04d}"
        _events_db.append(event)
    return {"status": "created", "count": len(events)}
