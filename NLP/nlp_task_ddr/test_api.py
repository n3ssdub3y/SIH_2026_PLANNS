import urllib.request, json
base = "http://localhost:5001"

r = urllib.request.urlopen(base+"/api/wells")
d = json.loads(r.read())
print(f"GET /api/wells -> {d['count']} wells OK")

url = base+"/api/analogs?well_id=7%2F1-2+S&hazard=stuck_pipe&top=3"
r = urllib.request.urlopen(url)
d = json.loads(r.read())
print(f"GET /api/analogs -> target={d['target_well']}, hazard={d['hazard']}, results={len(d['analogs'])}")
print(f"  Top analog: {d['analogs'][0]['well_id']}  score={d['analogs'][0]['weighted_score']}")

r = urllib.request.urlopen(base+"/api/search/formation?q=Aasgard")
d = json.loads(r.read())
print(f"GET /api/search/formation?q=Aasgard -> {d['count']} results")

r = urllib.request.urlopen(base+"/api/ahp_weights")
d = json.loads(r.read())
print(f"GET /api/ahp_weights -> {len(d)} hazards returned")

print("\nAll Flask API endpoints: OK")
