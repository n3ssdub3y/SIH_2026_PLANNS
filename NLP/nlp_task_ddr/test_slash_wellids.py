import urllib.request, json
base = "http://localhost:5001"

# Test the well IDs with slashes that were all 404-ing before
test_wells = ["16/4-1", "15/9-F-9A", "7/1-1", "34/3-2 S"]

print("Testing /api/well?well_id= (query param - the fix):")
for wid in test_wells:
    url = base + "/api/well?well_id=" + urllib.request.quote(wid)
    try:
        r = urllib.request.urlopen(url)
        d = json.loads(r.read())
        print(f"  OK  {wid:<20} -> source={d.get('source')} depth={d.get('total_depth_m')}")
    except Exception as e:
        print(f"  FAIL {wid:<20} -> {e}")

print()
print("All well-id-with-slash tests done!")
