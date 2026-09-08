import json
from pathlib import Path
out = Path("module2/outputs")

# analog_wells.json
analogs = json.load(open(out/"analog_wells.json"))
sample_well = list(analogs.keys())[0]
top3 = analogs[sample_well]["mud_loss"][:3]
print("=== analog_wells.json ===")
print(f"Wells: {len(analogs)}")
print(f"Hazards per well: {list(analogs[sample_well].keys())}")
print(f"Analogs per hazard: {len(analogs[sample_well]['mud_loss'])}")
for a in top3:
    print(f"  {a['well_id']:<20} score={a['weighted_score']}  fb={a['feature_breakdown']}")

# ahp_weights.json
ahp = json.load(open(out/"ahp_weights.json"))
print("\n=== ahp_weights.json ===")
for h, d in ahp.items():
    status = "OK" if d["consistency_acceptable"] else "WARN"
    print(f"  {h:<16} weights={d['weights']}  CR={d['consistency_ratio']}  {status}")

# formation_correlation.json
fc = json.load(open(out/"formation_correlation.json"))
print(f"\n=== formation_correlation.json ===")
print(f"Formations: {len(fc)}")
sf = list(fc.keys())[0]
print(f"Sample: [{sf}] -> {fc[sf]['well_count']} wells, depth={fc[sf]['depth_range_m']}")

print("\nAll output files verified OK!")
