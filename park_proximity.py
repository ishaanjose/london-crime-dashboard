"""
park_proximity.py

Computes distance from each London LSOA to its nearest park
(from OpenStreetMap) and updates the lsoa_stats table.
Then prints RQ4 results.

Run once: python3 park_proximity.py
"""
import sqlite3
import time
import requests
import numpy as np
import pandas as pd

DB_PATH = "street_crime.db"
NEAR_THRESHOLD = 500   # metres
YEARS = 3.0            # 36 months of data
BATCH_SIZE = 50

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "LondonCrimeDashboard/1.0"}

ARCGIS_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BFE_V10/"
    "FeatureServer/0/query"
)

# London bounding box
LONDON_BBOX = "51.28,-0.51,51.70,0.33"


def haversine(lat1, lon1, lat2, lon2):
    # Great-circle distance in metres. Vectorised over arrays.
    R = 6371000
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def fetch_centroids(lsoa_codes):
    # ArcGIS LSOA boundary service. Batch the codes to stay under URL length limits.
    rows = []
    batches = [lsoa_codes[i:i + BATCH_SIZE] for i in range(0, len(lsoa_codes), BATCH_SIZE)]
    print(f"Fetching {len(lsoa_codes)} centroids in {len(batches)} batches...")
    for i, batch in enumerate(batches):
        where = "LSOA21CD IN ('" + "','".join(batch) + "')"
        r = requests.get(ARCGIS_URL, params={
            "where": where,
            "outFields": "LSOA21CD,LAT,LONG",
            "returnGeometry": "false",
            "f": "json"
        }, timeout=30)
        for feat in r.json().get("features", []):
            a = feat["attributes"]
            rows.append({"lsoa_code": a["LSOA21CD"], "lat": a["LAT"], "lon": a["LONG"]})
        if i % 20 == 0:
            print(f"  {len(rows)} centroids so far")
        time.sleep(0.1)
    return pd.DataFrame(rows)


def fetch_parks():
    # Overpass query for all leisure=park features in the London bbox.
    query = f"""
    [out:json][timeout:60];
    (
      way[leisure=park]({LONDON_BBOX});
      node[leisure=park]({LONDON_BBOX});
    );
    out center;
    """
    r = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=90)
    parks = []
    for e in r.json()["elements"]:
        # Nodes have lat/lon directly; ways carry it on the 'center' field via 'out center'
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lon = e.get("lon") or (e.get("center") or {}).get("lon")
        name = (e.get("tags") or {}).get("name", "Unknown park")
        if lat and lon:
            parks.append({"name": name, "lat": lat, "lon": lon})
    return pd.DataFrame(parks)


def main():
    print("Fetching London parks from OpenStreetMap...")
    parks = fetch_parks()
    print(f"  {len(parks)} parks with coordinates")

    conn = sqlite3.connect(DB_PATH, timeout=30)

    lsoa_codes = pd.read_sql(
        "SELECT lsoa_code FROM lsoa_stats WHERE is_london = 1", conn
    )["lsoa_code"].tolist()
    print(f"{len(lsoa_codes)} London LSOAs")

    centroids = fetch_centroids(lsoa_codes)
    print(f"{len(centroids)} centroids returned")

    # Compute nearest park for each LSOA
    print("\nComputing distances...")
    p_lat = parks["lat"].values
    p_lon = parks["lon"].values

    dist_m, nearest, count_1km = [], [], []
    for _, row in centroids.iterrows():
        d = haversine(row["lat"], row["lon"], p_lat, p_lon)
        i = int(np.argmin(d))
        dist_m.append(round(float(d[i]), 1))
        nearest.append(parks.iloc[i]["name"])
        count_1km.append(int(np.sum(d <= 1000)))

    centroids["distance_to_park_m"] = dist_m
    centroids["nearest_park"] = nearest
    centroids["parks_within_1km"] = count_1km
    centroids["near_park"] = (centroids["distance_to_park_m"] <= NEAR_THRESHOLD).astype(int)

    print(f"  Near (<= {NEAR_THRESHOLD}m): {(centroids['near_park'] == 1).sum()}")
    print(f"  Far  (>  {NEAR_THRESHOLD}m): {(centroids['near_park'] == 0).sum()}")
    print(f"  Distance range: {centroids['distance_to_park_m'].min():.0f}m to "
          f"{centroids['distance_to_park_m'].max():.0f}m")

    # Update DB. Clear old values first so non-London rows go NULL.
    print("\nUpdating lsoa_stats...")
    conn.execute("""
        UPDATE lsoa_stats
        SET distance_to_park_m = NULL,
            nearest_park = NULL,
            near_park = NULL,
            parks_within_1km = NULL
    """)

    cols = ["lsoa_code", "distance_to_park_m", "nearest_park",
            "near_park", "parks_within_1km"]
    centroids[cols].to_sql("_park_tmp", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX idx_park_tmp_lsoa ON _park_tmp(lsoa_code)")
    conn.execute("""
        UPDATE lsoa_stats SET
            distance_to_park_m = (SELECT distance_to_park_m FROM _park_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code),
            nearest_park       = (SELECT nearest_park       FROM _park_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code),
            near_park          = (SELECT near_park          FROM _park_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code),
            parks_within_1km   = (SELECT parks_within_1km   FROM _park_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code)
        WHERE lsoa_stats.lsoa_code IN (SELECT lsoa_code FROM _park_tmp)
    """)
    conn.execute("DROP TABLE _park_tmp")
    conn.commit()
    print("  done")

    # RQ4: near vs far overall (population-weighted rate)
    print("\nRQ4: Near vs Far Park (weighted)")
    overall = pd.read_sql(f"""
        SELECT
            near_park,
            COUNT(*) AS n_lsoas,
            SUM(population) AS total_pop,
            SUM(total_crimes) AS total_crimes,
            ROUND(SUM(total_crimes) * 1000.0 / SUM(population) / {YEARS}, 2) AS annual_rate_per_1k
        FROM lsoa_stats
        WHERE is_outlier = 0 AND is_london = 1 AND near_park IS NOT NULL
        GROUP BY near_park
    """, conn)
    overall["near_park"] = overall["near_park"].map({
        1: f"Near (<= {NEAR_THRESHOLD}m)",
        0: f"Far  (>  {NEAR_THRESHOLD}m)",
    })
    print(overall.to_string(index=False))

    # RQ4: by crime type (weighted)
    print("\nRQ4: By Crime Type (weighted)")
    breakdown = pd.read_sql(f"""
        SELECT
            c.crime_type,
            s.near_park,
            COUNT(*) AS crime_count,
            (SELECT SUM(population) FROM lsoa_stats
             WHERE is_outlier = 0 AND is_london = 1 AND near_park = s.near_park) AS group_pop
        FROM crimes c
        JOIN lsoa_stats s ON c.lsoa = s.lsoa_code
        WHERE s.is_outlier = 0 AND s.is_london = 1 AND s.near_park IS NOT NULL
        GROUP BY c.crime_type, s.near_park
    """, conn)
    breakdown["rate"] = breakdown["crime_count"] * 1000.0 / breakdown["group_pop"] / YEARS

    pivot = breakdown.pivot(index="crime_type", columns="near_park", values="rate")
    pivot.columns = ["Far (>500m)", "Near (<=500m)"]
    pivot["diff"] = pivot["Near (<=500m)"] - pivot["Far (>500m)"]
    pivot["ratio"] = (pivot["Near (<=500m)"] / pivot["Far (>500m)"]).round(2)
    pivot["pct"] = ((pivot["ratio"] - 1) * 100).round(1).astype(str) + "%"
    pivot = pivot.sort_values("ratio", ascending=False)
    print(pivot.round(2).to_string())

    # RQ4: density bands (weighted)
    print("\nRQ4: Park density bands (weighted)")
    density = pd.read_sql(f"""
        SELECT
            CASE
                WHEN parks_within_1km = 0             THEN '0 parks'
                WHEN parks_within_1km BETWEEN 1 AND 3 THEN '1-3 parks'
                WHEN parks_within_1km BETWEEN 4 AND 7 THEN '4-7 parks'
                ELSE '8+ parks'
            END AS band,
            COUNT(*) AS n_lsoas,
            ROUND(SUM(total_crimes) * 1000.0 / SUM(population) / {YEARS}, 2) AS annual_rate_per_1k
        FROM lsoa_stats
        WHERE is_outlier = 0 AND is_london = 1 AND parks_within_1km IS NOT NULL
        GROUP BY band
        ORDER BY annual_rate_per_1k
    """, conn)
    print(density.to_string(index=False))

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()