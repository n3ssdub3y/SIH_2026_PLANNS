"""
Fix: Volve well 15/9-F-9A has lon=7.93482 because its UTM coords
were accidentally converted using Zone 32N instead of correct Zone 31N.

Approach:
  1. Take the wrong lat/lon (58.375409, 7.93482)
  2. Back-project to UTM using Zone 32N  ->  get raw Easting, Northing
  3. Re-project those same E/N using Zone 31N (the correct zone)
  4. Result = correct lat/lon
"""
from pyproj import Proj, Transformer

# Wrong coordinates (Zone 32N misapplied)
wrong_lat = 58.375409
wrong_lon = 7.93482

# Step 1: lat/lon -> UTM 32N  (undo the wrong projection)
to_utm32 = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
easting, northing = to_utm32.transform(wrong_lon, wrong_lat)
print(f"Raw UTM coords  ->  Easting={easting:.2f}  Northing={northing:.2f}")

# Step 2: same E/N -> lat/lon using Zone 31N (correct projection)
from_utm31 = Transformer.from_crs("EPSG:32631", "EPSG:4326", always_xy=True)
correct_lon, correct_lat = from_utm31.transform(easting, northing)
print(f"Corrected coords (Zone 31N)  ->  lat={correct_lat:.6f}  lon={correct_lon:.6f}")
print()
print(f"Old: lat={wrong_lat}, lon={wrong_lon}")
print(f"New: lat={correct_lat:.6f}, lon={correct_lon:.6f}")
print(f"Shift: {correct_lon - wrong_lon:.4f}° in longitude")
