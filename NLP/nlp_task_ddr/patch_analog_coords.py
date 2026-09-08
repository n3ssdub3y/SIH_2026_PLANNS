import json
from pathlib import Path

path = Path("module2/outputs/analog_wells.json")
print("Loading analog_wells.json...")
analogs = json.load(open(path, encoding="utf-8"))

fixed = 0
for wid, hazards in analogs.items():
    for h, alist in hazards.items():
        for a in alist:
            if a["well_id"] == "15/9-F-9A" and abs(a.get("longitude", 0) - 7.93482) < 0.001:
                a["longitude"] = 1.934820
                fixed += 1

print(f"Patched {fixed} entries in analog_wells.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(analogs, f, ensure_ascii=False)
print("Saved.")
