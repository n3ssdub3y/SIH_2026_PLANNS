import urllib.request, json

# Test the main page loads
r = urllib.request.urlopen("http://localhost:5001/")
code = r.getcode()
body = r.read().decode()
print(f"GET / -> HTTP {code}")
print(f"  Contains 'custom-select-btn': {'custom-select-btn' in body}")
print(f"  Contains 'highlightAnalog': {'highlightAnalog' in body}")
print(f"  Contains 'buildDropdown': {'buildDropdown' in body}")
print(f"  Contains 'well-search-input': {'well-search-input' in body}")

# Test wells API
r2 = urllib.request.urlopen("http://localhost:5001/api/wells")
d = json.loads(r2.read())
print(f"\nGET /api/wells -> {d['count']} wells")
print(f"  First 3: {[w['well_id'] for w in d['wells'][:3]]}")
