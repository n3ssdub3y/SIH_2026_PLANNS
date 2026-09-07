"""Matching router — analog well discovery and LLM briefing."""

from fastapi import APIRouter, Query
from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.demo_data import DEMO_WELLS, DEMO_EVENTS, DEMO_SCENARIOS
from app.services.similarity_engine import Well, find_analogs, check_analog_disagreement

router = APIRouter()


def _well_dict_to_obj(d: dict) -> Well:
    """Convert dict to Well dataclass."""
    return Well(
        well_id=d["well_id"],
        name=d["name"],
        latitude=d["latitude"],
        longitude=d["longitude"],
        total_depth_m=d["total_depth_m"],
        formations=d.get("formations", []),
        formation_tops_m=d.get("formation_tops_m", []),
        spud_date=d.get("spud_date"),
        status=d.get("status", "completed")
    )


def _run_matching(well_id: str, depth_m: float, hazard_type: str,
                  formation: Optional[str] = None,
                  mud_weight_sg: Optional[float] = None, top_k: int = 5) -> dict:
    """Core matching logic — shared by /analogs and /scenarios endpoints."""
    active_dict = None
    for w in DEMO_WELLS:
        if w["well_id"] == well_id:
            active_dict = w
            break

    if not active_dict:
        return {"error": f"Well {well_id} not found"}

    active_well = _well_dict_to_obj(active_dict)
    wells_db = [_well_dict_to_obj(w) for w in DEMO_WELLS]

    # Auto-detect formation from depth if not provided
    if formation is None and active_dict.get("formations") and active_dict.get("formation_tops_m"):
        for i, top in enumerate(active_dict["formation_tops_m"]):
            if depth_m >= top:
                formation = active_dict["formations"][i]

    # Run matching
    analogs = find_analogs(
        active_well=active_well,
        active_depth_m=depth_m,
        active_formation=formation,
        hazard_type=hazard_type,
        wells_db=wells_db,
        events_db=DEMO_EVENTS,
        top_k=top_k,
        active_mud_weight=mud_weight_sg
    )

    # Check disagreement
    disagreement = check_analog_disagreement(analogs, hazard_type)

    return {
        "active_well": well_id,
        "depth_m": depth_m,
        "formation": formation,
        "hazard_type": hazard_type,
        "analogs": [
            {
                "well_id": a.well.well_id,
                "name": a.well.name,
                "score": round(a.overall_score, 3),
                "feature_scores": {k: round(v, 3) for k, v in a.feature_scores.items()},
                "matched_events_count": len(a.matched_events),
                "matched_events": a.matched_events,
                "explanation": a.explanation
            }
            for a in analogs
        ],
        "disagreement": disagreement,
        "total_candidates": len(DEMO_WELLS) - 1
    }


@router.get("/analogs")
def get_analogs(
    well_id: str = Query(..., description="Active well ID"),
    depth_m: float = Query(..., description="Current drilling depth in meters"),
    hazard_type: str = Query("mud_loss", description="Hazard type: mud_loss, stuck_pipe, kick"),
    formation: Optional[str] = Query(None, description="Current formation name"),
    mud_weight_sg: Optional[float] = Query(None, description="Current mud weight in SG"),
    top_k: int = Query(5, description="Number of analogs to return")
):
    """
    Find top-k analog wells for the active well at the given depth and hazard type.
    THIS IS THE CORE API — the "intelligence" endpoint that powers the demo.
    """
    return _run_matching(well_id, depth_m, hazard_type, formation, mud_weight_sg, top_k)


@router.get("/scenarios")
def list_scenarios():
    """List pre-scripted demo scenarios."""
    return {"scenarios": DEMO_SCENARIOS}


@router.get("/scenarios/{scenario_id}")
def run_scenario(scenario_id: str):
    """Run a pre-scripted demo scenario — returns the full matching result."""
    scenario = None
    for s in DEMO_SCENARIOS:
        if s["scenario_id"] == scenario_id:
            scenario = s
            break

    if not scenario:
        return {"error": f"Scenario {scenario_id} not found"}

    trigger = scenario["trigger"]
    result = _run_matching(
        well_id=trigger["active_well"],
        depth_m=trigger["depth_m"],
        hazard_type=trigger["hazard_type"],
        formation=trigger.get("formation")
    )

    result["scenario"] = scenario
    return result

