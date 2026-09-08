import json
from pathlib import Path

path = Path("results/module1_outputs/wells_metadata.json")
wells = json.load(open(path, encoding="utf-8"))

fixed = 0
for w in wells:
    if w["well_id"] == "15/9-F-9A" and w["source"] == "real_volve":
        print(f"BEFORE: well_id={w['well_id']}  lat={w['latitude']}  lon={w['longitude']}")
        w["longitude"] = 1.934820   # corrected Zone 31N value
        w["_coord_note"] = "Longitude corrected from 7.93482 (Zone 32N error) to 1.934820 (Zone 31N correct)"
        print(f"AFTER:  well_id={w['well_id']}  lat={w['latitude']}  lon={w['longitude']}")
        fixed += 1

with open(path, "w", encoding="utf-8") as f:
    json.dump(wells, f, ensure_ascii=False)

print(f"\nFixed {fixed} well(s). File saved.")
