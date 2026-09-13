import urllib.request, json, sys

# Dynamic URL: default to unified gateway (5000), fall back to standalone (5001)
base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
test_url = f"{base}/module2/" if "5000" in base else f"{base}/"

try:
    r = urllib.request.urlopen(test_url)
except Exception:
    base = "http://localhost:5001"
    test_url = f"{base}/"
    r = urllib.request.urlopen(test_url)

code = r.getcode()
body = r.read().decode()
print(f"GET {test_url} -> HTTP {code}")
print(f"  Contains 'custom-select-btn': {'custom-select-btn' in body}")
print(f"  Contains 'highlightAnalog': {'highlightAnalog' in body}")
print(f"  Contains 'buildDropdown': {'buildDropdown' in body}")
print(f"  Contains 'well-search-input': {'well-search-input' in body}")

# Test wells API
wells_url = f"{base}/api/wells"
r2 = urllib.request.urlopen(wells_url)
d = json.loads(r2.read())
print(f"\nGET {wells_url} -> {d['count']} wells")
print(f"  First 3: {[w['well_id'] for w in d['wells'][:3]]}")
