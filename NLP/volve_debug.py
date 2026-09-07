"""
Debug: List everything available in the Volve Delta Sharing endpoint
"""
import delta_sharing
import sys

sys.stdout.reconfigure(encoding='utf-8')

SHARE_FILE = r"d:\New_folder\Desktop\SIH\Volve_Data_Village_WCR.share"

print("Connecting...")
client = delta_sharing.SharingClient(SHARE_FILE)

# List all shares
shares = client.list_shares()
print(f"\nShares ({len(shares)}):")
for s in shares:
    print(f"  Share: {s.name}")

# List all tables (the simpler API)
print("\n--- Listing ALL tables via list_all_tables() ---\n")
try:
    all_tables = client.list_all_tables()
    print(f"Total tables: {len(all_tables)}")
    for t in all_tables:
        print(f"  {t.share}.{t.schema}.{t.name}")
except Exception as e:
    print(f"list_all_tables() failed: {e}")

# Also try listing schemas per share manually
print("\n--- Listing schemas per share ---\n")
for s in shares:
    try:
        schemas = client.list_schemas(s)
        print(f"  Share '{s.name}' has {len(schemas)} schema(s):")
        for sc in schemas:
            print(f"    Schema: {sc.name}")
            try:
                tables = client.list_tables(sc)
                print(f"      Tables ({len(tables)}):")
                for t in tables:
                    print(f"        -> {t.name}")
            except Exception as e2:
                print(f"      Error listing tables: {e2}")
    except Exception as e:
        print(f"  Error listing schemas for '{s.name}': {e}")
