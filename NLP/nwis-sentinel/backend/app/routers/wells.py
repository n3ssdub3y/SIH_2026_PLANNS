"""Wells router — GET all wells, GET single well."""

from fastapi import APIRouter, HTTPException
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data.demo_data import DEMO_WELLS

router = APIRouter()


@router.get("/")
def list_wells():
    """Return all wells in the system."""
    return {"wells": DEMO_WELLS, "count": len(DEMO_WELLS)}


@router.get("/{well_id}")
def get_well(well_id: str):
    """Return a single well by ID."""
    for w in DEMO_WELLS:
        if w["well_id"] == well_id:
            return w
    raise HTTPException(status_code=404, detail=f"Well {well_id} not found")


@router.get("/{well_id}/nearby")
def get_nearby_wells(well_id: str, radius_km: float = 5.0):
    """Return wells within radius_km of the given well."""
    import math
    
    target = None
    for w in DEMO_WELLS:
        if w["well_id"] == well_id:
            target = w
            break
    
    if not target:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    
    nearby = []
    for w in DEMO_WELLS:
        if w["well_id"] == well_id:
            continue
        dist = haversine(target["latitude"], target["longitude"], w["latitude"], w["longitude"])
        if dist <= radius_km:
            nearby.append({**w, "distance_km": round(dist, 2)})
    
    nearby.sort(key=lambda x: x["distance_km"])
    return {"well": target, "nearby": nearby, "radius_km": radius_km}
