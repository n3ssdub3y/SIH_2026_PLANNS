import json
wells = json.load(open("results/module1_outputs/wells_metadata.json"))
volve = [w for w in wells if w["source"] == "real_volve"]
print(f"Total real_volve wells: {len(volve)}")
for w in volve:
    lat = w.get("latitude")
    lon = w.get("longitude")
    print(f"  {w['well_id']:<20} lat={lat}  lon={lon}  synth={w['is_synthetic']}")
