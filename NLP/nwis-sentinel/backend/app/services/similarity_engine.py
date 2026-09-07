"""
NWIS-Sentinel: Similarity & Analog Matching Engine (P2's core module)
Hazard-specific weighted similarity scoring + event-sequence alignment.

Usage:
    from services.similarity_engine import find_analogs
    analogs = find_analogs(active_well, hazard_type="mud_loss", wells_db=wells, events_db=events)
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------- WELL DATA MODEL ----------
@dataclass
class Well:
    well_id: str
    name: str
    latitude: float
    longitude: float
    total_depth_m: float
    formations: list[str] = field(default_factory=list)     # formation names top-to-bottom
    formation_tops_m: list[float] = field(default_factory=list)  # depths where formations start
    spud_date: Optional[str] = None
    status: str = "completed"  # completed, drilling, abandoned


@dataclass 
class AnalogResult:
    well: Well
    overall_score: float        # 0-1, higher = better analog
    feature_scores: dict        # breakdown by feature
    matched_events: list[dict]  # events at similar depths/formations
    explanation: str            # human-readable justification


# ---------- HAZARD-SPECIFIC FEATURE WEIGHTS ----------
# These weights determine WHICH features matter for EACH hazard type.
# Source: Public drilling-engineering literature (cite in PPT!)
# Reference: SPE papers on offset-well selection methodology

HAZARD_WEIGHTS = {
    "mud_loss": {
        "formation_match":     0.30,  # Same formation = most predictive of mud loss
        "depth_proximity":     0.25,  # Similar depth range
        "mud_weight_match":    0.20,  # Similar mud weight used
        "spatial_distance":    0.15,  # Geographic proximity
        "lithology_match":     0.10,  # Similar rock type
    },
    "stuck_pipe": {
        "formation_match":     0.25,
        "depth_proximity":     0.20,
        "bha_similarity":      0.15,  # Similar BHA/drillstring
        "mud_weight_match":    0.15,
        "hole_angle_match":    0.10,  # Directional similarity
        "spatial_distance":    0.15,
    },
    # Default weights for other hazard types
    "default": {
        "formation_match":     0.30,
        "depth_proximity":     0.25,
        "spatial_distance":    0.20,
        "mud_weight_match":    0.15,
        "lithology_match":     0.10,
    }
}


# ---------- FEATURE SCORING FUNCTIONS ----------
def score_formation_match(active_formation: Optional[str], 
                          candidate_formations: list[str]) -> float:
    """Score how well formations match. 1.0 = exact match, 0.0 = no match."""
    if not active_formation or not candidate_formations:
        return 0.3  # Neutral if unknown
    
    if active_formation.lower() in [f.lower() for f in candidate_formations]:
        return 1.0
    return 0.0


def score_depth_proximity(active_depth_m: float,
                          candidate_events: list[dict],
                          max_distance_m: float = 500) -> float:
    """Score based on how close candidate events are to the active depth."""
    if not candidate_events:
        return 0.0
    
    min_distance = min(
        abs(active_depth_m - evt.get("depth_start_m", 0))
        for evt in candidate_events
        if evt.get("depth_start_m") is not None
    ) if any(evt.get("depth_start_m") is not None for evt in candidate_events) else max_distance_m
    
    # Linear decay: 0m = 1.0, max_distance_m = 0.0
    return max(0.0, 1.0 - (min_distance / max_distance_m))


def score_spatial_distance(lat1: float, lon1: float,
                           lat2: float, lon2: float,
                           max_distance_km: float = 10.0) -> float:
    """Score based on geographic distance (Haversine). Closer = higher."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2)**2)
    distance_km = R * 2 * math.asin(math.sqrt(a))
    
    return max(0.0, 1.0 - (distance_km / max_distance_km))


def score_mud_weight_match(active_mw: Optional[float],
                           candidate_events: list[dict],
                           tolerance_sg: float = 0.2) -> float:
    """Score based on mud weight similarity."""
    if active_mw is None:
        return 0.5  # Neutral
    
    candidate_mws = [
        evt.get("parameters", {}).get("mud_weight_sg")
        for evt in candidate_events
        if evt.get("parameters") and evt["parameters"].get("mud_weight_sg") is not None
    ]
    
    if not candidate_mws:
        return 0.3
    
    min_diff = min(abs(active_mw - mw) for mw in candidate_mws)
    return max(0.0, 1.0 - (min_diff / tolerance_sg))


# ---------- MAIN MATCHING FUNCTION ----------
def find_analogs(
    active_well: Well,
    active_depth_m: float,
    active_formation: Optional[str],
    hazard_type: str,
    wells_db: list[Well],
    events_db: list[dict],
    top_k: int = 5,
    active_mud_weight: Optional[float] = None
) -> list[AnalogResult]:
    """
    Find the top-k analog wells for a given active well, depth, and hazard type.
    
    This is the CORE INTELLIGENCE of the NWIS system — it produces a hazard-specific
    ranked list of offset wells, not a generic similarity score.
    
    Args:
        active_well: The well currently being drilled
        active_depth_m: Current drilling depth
        active_formation: Current formation (if known)
        hazard_type: "mud_loss" or "stuck_pipe" (determines feature weights)
        wells_db: List of all historical wells
        events_db: List of all historical events (conforming to event_schema.json)
        top_k: Number of analogs to return
        active_mud_weight: Current mud weight in SG (if known)
    
    Returns:
        List of AnalogResult, sorted by score (highest first)
    """
    weights = HAZARD_WEIGHTS.get(hazard_type, HAZARD_WEIGHTS["default"])
    results = []
    
    for candidate in wells_db:
        # Skip self
        if candidate.well_id == active_well.well_id:
            continue
        
        # Get events for this candidate well, filtered by hazard type
        candidate_events = [
            e for e in events_db
            if e["well_id"] == candidate.well_id and e["event_type"] == hazard_type
        ]
        
        # Also get ALL events at similar depths (for context)
        candidate_events_at_depth = [
            e for e in events_db
            if e["well_id"] == candidate.well_id
            and e.get("depth_start_m") is not None
            and abs(e["depth_start_m"] - active_depth_m) < 500
        ]
        
        # Score each feature
        feature_scores = {}
        
        if "formation_match" in weights:
            feature_scores["formation_match"] = score_formation_match(
                active_formation, candidate.formations
            )
        
        if "depth_proximity" in weights:
            feature_scores["depth_proximity"] = score_depth_proximity(
                active_depth_m, candidate_events
            )
        
        if "spatial_distance" in weights:
            feature_scores["spatial_distance"] = score_spatial_distance(
                active_well.latitude, active_well.longitude,
                candidate.latitude, candidate.longitude
            )
        
        if "mud_weight_match" in weights:
            feature_scores["mud_weight_match"] = score_mud_weight_match(
                active_mud_weight, candidate_events
            )
        
        # Fill unscored features with neutral values
        for feat in weights:
            if feat not in feature_scores:
                feature_scores[feat] = 0.5
        
        # Compute weighted overall score
        overall_score = sum(
            weights[feat] * feature_scores.get(feat, 0.5)
            for feat in weights
        )
        
        # Build explanation
        top_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)
        explanation_parts = []
        for feat, score in top_features[:3]:
            if score > 0.7:
                explanation_parts.append(f"Strong {feat.replace('_', ' ')} ({score:.0%})")
            elif score < 0.3:
                explanation_parts.append(f"Weak {feat.replace('_', ' ')} ({score:.0%})")
        
        explanation = f"{candidate.name}: " + "; ".join(explanation_parts) if explanation_parts else f"{candidate.name}: moderate match"
        
        if candidate_events:
            explanation += f". {len(candidate_events)} historical {hazard_type.replace('_', ' ')} event(s) found."
        
        results.append(AnalogResult(
            well=candidate,
            overall_score=overall_score,
            feature_scores=feature_scores,
            matched_events=candidate_events_at_depth,
            explanation=explanation
        ))
    
    # Sort by score, return top-k
    results.sort(key=lambda x: x.overall_score, reverse=True)
    return results[:top_k]


def check_analog_disagreement(analogs: list[AnalogResult], hazard_type: str) -> dict:
    """
    Check if top analogs DISAGREE on outcomes — this is the uncertainty feature.
    If analogs disagree, the system flags it instead of averaging.
    
    Returns:
        {
            "agrees": bool,
            "outcomes": {"resolved": 2, "escalated": 1},
            "message": "Warning: analogs disagree on outcome..."
        }
    """
    outcomes = {}
    for analog in analogs[:3]:  # Check top 3
        for evt in analog.matched_events:
            if evt["event_type"] == hazard_type:
                outcome = evt.get("outcome", "unknown")
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
    
    if not outcomes:
        return {
            "agrees": True,
            "outcomes": {},
            "message": "No historical events found for comparison."
        }
    
    agrees = len(outcomes) <= 1
    
    if agrees:
        dominant = max(outcomes, key=outcomes.get)
        return {
            "agrees": True,
            "outcomes": outcomes,
            "message": f"Analogs agree: {hazard_type.replace('_', ' ')} events were typically {dominant}."
        }
    else:
        return {
            "agrees": False,
            "outcomes": outcomes,
            "message": f"WARNING: Analogs disagree on {hazard_type.replace('_', ' ')} outcomes. "
                       f"Outcomes observed: {', '.join(f'{k} ({v}x)' for k, v in outcomes.items())}. "
                       f"Manual review recommended."
        }
