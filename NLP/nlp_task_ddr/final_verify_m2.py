"""Final verification checklist for Module 2 handoff to P3"""
import json, os
from pathlib import Path

OK = True
results = []

def check(name, cond, detail=""):
    global OK
    status = "PASS" if cond else "FAIL"
    if not cond: OK = False
    results.append((status, name, detail))

base = Path("module2")

# --- Files exist ---
check("compute_similarity.py exists", (base/"compute_similarity.py").exists())
check("app.py exists",                (base/"app.py").exists())
check("map.html exists",              (base/"templates/map.html").exists())
check("analog_wells.json exists",     (base/"outputs/analog_wells.json").exists())
check("ahp_weights.json exists",      (base/"outputs/ahp_weights.json").exists())
check("formation_correlation.json exists", (base/"outputs/formation_correlation.json").exists())
check("README_module2 exists",        (base/"README_module2_geospatial_and_similarity.md").exists())

# --- analog_wells.json content ---
analogs = json.load(open(base/"outputs/analog_wells.json"))
check("analog_wells: 159 wells",      len(analogs) == 159, f"got {len(analogs)}")
HAZARDS = ["mud_loss","stuck_pipe","overpressure","torque_spike","cementing"]
first = list(analogs.values())[0]
check("analog_wells: 5 hazards per well", set(first.keys()) == set(HAZARDS))
check("analog_wells: 158 analogs per hazard", len(first["mud_loss"]) == 158)

# Check schema of one entry
entry = first["mud_loss"][0]
check("analog_wells entry has weighted_score",    "weighted_score" in entry)
check("analog_wells entry has feature_breakdown", "feature_breakdown" in entry)
check("analog_wells entry has ahp_weights_used",  "ahp_weights_used" in entry)
check("analog_wells entry has is_synthetic flag", "is_synthetic" in entry)
fb = entry["feature_breakdown"]
check("feature_breakdown has 5 features", len(fb) == 5)
for v in fb.values():
    check(f"feature value in [0,1]: {v:.3f}", 0.0 <= v <= 1.0, str(v))

# --- ahp_weights.json content ---
ahp = json.load(open(base/"outputs/ahp_weights.json"))
check("ahp_weights: 5 hazards",      len(ahp) == 5)
for h, d in ahp.items():
    check(f"AHP CR acceptable for {h}", d["consistency_acceptable"], f"CR={d['consistency_ratio']}")
    wts = d["weights_vector"]
    check(f"AHP weights sum to ~1 for {h}", abs(sum(wts)-1.0) < 0.001, str(sum(wts)))

# --- formation_correlation.json ---
fc = json.load(open(base/"outputs/formation_correlation.json"))
check("formation_correlation: >= 50 formations", len(fc) >= 50, f"got {len(fc)}")
for name, data in list(fc.items())[:3]:
    check(f"formation has well_count for {name[:20]}", "well_count" in data)
    check(f"formation has depth_range for {name[:20]}", "depth_range_m" in data)

# --- Print results ---
print("=" * 60)
print("Module 2 — Final Verification Report")
print("=" * 60)
for status, name, detail in results:
    icon = "OK  " if status == "PASS" else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{icon}] {name}{suffix}")

print("=" * 60)
if OK:
    print("ALL CHECKS PASSED - Ready to hand off to P3!")
else:
    failed = [r for r in results if r[0]=="FAIL"]
    print(f"FAILED: {len(failed)} checks failed")
