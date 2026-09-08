import json
from pathlib import Path

# Check if analog_wells.json still has old Volve coords embedded
analogs = json.load(open("module2/outputs/analog_wells.json"))

# Find 15/9-F-9A as a TARGET well
target = analogs.get("15/9-F-9A", {})
if target:
    sample = target.get("mud_loss", [{}])[0]
    print(f"15/9-F-9A as TARGET - first analog lat/lon not stored here, just the target well metadata comes from wells_metadata.json")

# Find 15/9-F-9A as an ANALOG in another well's list
found_as_analog = []
for wid, hazards in list(analogs.items())[:10]:
    for h, alist in hazards.items():
        for a in alist:
            if a["well_id"] == "15/9-F-9A":
                found_as_analog.append((wid, h, a.get("latitude"), a.get("longitude")))
                break

print(f"\n15/9-F-9A appearing as ANALOG in other wells (sample):")
for wid, h, lat, lon in found_as_analog[:3]:
    print(f"  In well={wid} hazard={h}: lat={lat} lon={lon}")

print("\n--- Fields stored per analog entry ---")
sample_well = list(analogs.keys())[0]
sample_entry = analogs[sample_well]["mud_loss"][0]
print(f"Keys: {list(sample_entry.keys())}")
