"""Quick test of the NWIS-Sentinel API endpoints."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import urllib.request

BASE = "http://localhost:8000"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

# Test 1: Root
print("=== ROOT ===")
print(json.dumps(get("/"), indent=2))

# Test 2: Wells
print("\n=== WELLS ===")
wells = get("/api/wells")
for w in wells["wells"]:
    print(f"  {w['well_id']}: {w['name']} ({w['latitude']}, {w['longitude']}) - {w['status']}")

# Test 3: Events
print("\n=== EVENTS SUMMARY ===")
summary = get("/api/events/summary")
print(f"  Total events: {summary['total_events']}")
print(f"  By type: {summary['by_type']}")
print(f"  By well: {summary['by_well']}")

# Test 4: CORE - Analog matching (mud loss)
print("\n=== MUD LOSS ANALOGS at 2200m ===")
analogs_ml = get("/api/matching/analogs?well_id=WELL-F9A&depth_m=2200&hazard_type=mud_loss")
print(f"  Formation: {analogs_ml['formation']}")
for i, a in enumerate(analogs_ml["analogs"]):
    print(f"  #{i+1} {a['name']} - Score: {a['score']} - Events: {a['matched_events_count']}")
    print(f"       {a['explanation']}")
print(f"  Disagreement: {analogs_ml['disagreement']['message']}")

# Test 5: CORE - SAME query but STUCK PIPE (the WOW moment!)
print("\n=== STUCK PIPE ANALOGS at 2200m (SAME depth, DIFFERENT hazard) ===")
analogs_sp = get("/api/matching/analogs?well_id=WELL-F9A&depth_m=2200&hazard_type=stuck_pipe")
for i, a in enumerate(analogs_sp["analogs"]):
    print(f"  #{i+1} {a['name']} - Score: {a['score']} - Events: {a['matched_events_count']}")

# Compare rankings
print("\n=== WOW MOMENT: Rankings CHANGED! ===")
ml_order = [a["well_id"] for a in analogs_ml["analogs"]]
sp_order = [a["well_id"] for a in analogs_sp["analogs"]]
print(f"  Mud Loss ranking:  {ml_order}")
print(f"  Stuck Pipe ranking: {sp_order}")
if ml_order != sp_order:
    print("  >>> Rankings are DIFFERENT - hazard-specific matching works!")
else:
    print("  >>> Rankings are the same - need to tune weights")

# Test 6: Demo Scenario
print("\n=== DEMO SCENARIO 1 ===")
scenario = get("/api/matching/scenarios/SCENARIO_1")
print(f"  Name: {scenario['scenario']['name']}")
print(f"  WOW moment: {scenario['scenario']['wow_moment']}")
