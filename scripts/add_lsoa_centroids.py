"""
Idempotent: fetch LSOA centroids from ArcGIS and store them in lsoa_stats.
"""
import sqlite3
import pandas as pd
from scripts.station_proximity import fetch_centroids

DB_PATH = "data/street_crime.db"

conn = sqlite3.connect(DB_PATH, timeout=30)
cur = conn.cursor()

# Check actual schema
existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(lsoa_stats)")}

# Add lat/lon if missing
for col in ("lat", "lon"):
    if col not in existing_cols:
        cur.execute(f"ALTER TABLE lsoa_stats ADD COLUMN {col} REAL")
        print(f"Added column: {col}")
    else:
        print(f"Column {col} already exists")

conn.commit()
conn.close()


conn = sqlite3.connect(DB_PATH, timeout=30)
cur = conn.cursor()

#Fetch London LSOA codes
codes = pd.read_sql("SELECT lsoa_code FROM lsoa_stats WHERE is_london = 1", conn)["lsoa_code"].tolist()
print(f"\n{len(codes)} London LSOAs to fetch centroids for")

# Fetch centroids from ArcGIS
centroids = fetch_centroids(codes)
print(f"{len(centroids)} centroids returned")

# Write back
print("\nUpdating lsoa_stats...")
update_data = list(centroids[["lat", "lon", "lsoa_code"]].itertuples(index=False, name=None))
cur.executemany(
    "UPDATE lsoa_stats SET lat = ?, lon = ? WHERE lsoa_code = ?",
    update_data
)
conn.commit()
print(f"Rows affected: {cur.rowcount}")

# Verify
n, mnlat, mxlat, mnlon, mxlon = cur.execute("""
    SELECT COUNT(*), MIN(lat), MAX(lat), MIN(lon), MAX(lon)
    FROM lsoa_stats
    WHERE lat IS NOT NULL AND is_london = 1 AND is_outlier = 0
""").fetchone()
print(f"\nLondon non-outlier LSOAs with centroids: {n}")
if n > 0:
    print(f"Lat: {mnlat:.4f} → {mxlat:.4f}  (London ≈ 51.28 → 51.70)")
    print(f"Lon: {mnlon:.4f} → {mxlon:.4f}  (London ≈ -0.51 → 0.33)")

conn.close()
print("\nDone.")