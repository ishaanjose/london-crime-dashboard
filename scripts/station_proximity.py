"""
Computes distance from each London LSOA to its nearest TfL station
and updates the lsoa_stats table. Then prints RQ2 results.
"""
import sqlite3
import time
import requests
import numpy as np
import pandas as pd

DB_PATH = "data/street_crime.db"
NEAR_THRESHOLD = 500   # metres
YEARS = 3.0            
BATCH_SIZE = 50

ARCGIS_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BFE_V10/"
    "FeatureServer/0/query"
)


def haversine(lat1, lon1, lat2, lon2):
    # Great circle distance in metres. Vectorised over arrays.
    R = 6371000
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def fetch_centroids(lsoa_codes):
    # ArcGIS LSOA boundary service. Batch the codes to stay under URL length limits
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


def main():
    conn = sqlite3.connect(DB_PATH, timeout=30)

    # Load London LSOA codes and station coords
    lsoa_codes = pd.read_sql(
        "SELECT lsoa_code FROM lsoa_stats WHERE is_london = 1", conn
    )["lsoa_code"].tolist()
    print(f"{len(lsoa_codes)} London LSOAs")

    stations = pd.read_sql("SELECT name, lat, lon FROM stations", conn)
    print(f"{len(stations)} TfL stations")

    centroids = fetch_centroids(lsoa_codes)
    print(f"{len(centroids)} centroids returned")

    # Compute nearest station for each LSOA
    print("\nComputing distances...")
    s_lat = stations["lat"].values
    s_lon = stations["lon"].values

    dist_m, nearest, count_1km = [], [], []
    for _, row in centroids.iterrows():
        d = haversine(row["lat"], row["lon"], s_lat, s_lon)
        i = int(np.argmin(d))
        dist_m.append(round(float(d[i]), 1))
        nearest.append(stations.iloc[i]["name"])
        count_1km.append(int(np.sum(d <= 1000)))

    centroids["distance_to_station_m"] = dist_m
    centroids["nearest_station"] = nearest
    centroids["stations_within_1km"] = count_1km
    centroids["near_station"] = (centroids["distance_to_station_m"] <= NEAR_THRESHOLD).astype(int)

    print(f"  Near (<= {NEAR_THRESHOLD}m): {(centroids['near_station'] == 1).sum()}")
    print(f"  Far  (>  {NEAR_THRESHOLD}m): {(centroids['near_station'] == 0).sum()}")
    print(f"  Distance range: {centroids['distance_to_station_m'].min():.0f}m to "
          f"{centroids['distance_to_station_m'].max():.0f}m")

    # Update DB. Clear old values first so non-London rows go NULL.
    print("\nUpdating lsoa_stats...")
    conn.execute("""
        UPDATE lsoa_stats
        SET distance_to_station_m = NULL,
            nearest_station = NULL,
            near_station = NULL,
            stations_within_1km = NULL
    """)

    cols = ["lsoa_code", "distance_to_station_m", "nearest_station",
            "near_station", "stations_within_1km"]
    centroids[cols].to_sql("_stn_tmp", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX idx_stn_tmp_lsoa ON _stn_tmp(lsoa_code)")
    conn.execute("""
        UPDATE lsoa_stats SET
            distance_to_station_m = (SELECT distance_to_station_m FROM _stn_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code),
            nearest_station       = (SELECT nearest_station       FROM _stn_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code),
            near_station          = (SELECT near_station          FROM _stn_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code),
            stations_within_1km   = (SELECT stations_within_1km   FROM _stn_tmp t WHERE t.lsoa_code = lsoa_stats.lsoa_code)
        WHERE lsoa_stats.lsoa_code IN (SELECT lsoa_code FROM _stn_tmp)
    """)
    conn.execute("DROP TABLE _stn_tmp")
    conn.commit()
    print("  done")

    # RQ2: near vs far overall (population-weighted rate)
    print("\nRQ2: Near vs Far Station (weighted)")
    overall = pd.read_sql(f"""
        SELECT
            near_station,
            COUNT(*) AS n_lsoas,
            SUM(population) AS total_pop,
            SUM(total_crimes) AS total_crimes,
            ROUND(SUM(total_crimes) * 1000.0 / SUM(population) / {YEARS}, 2) AS annual_rate_per_1k
        FROM lsoa_stats
        WHERE is_outlier = 0 AND is_london = 1 AND near_station IS NOT NULL
        GROUP BY near_station
    """, conn)
    overall["near_station"] = overall["near_station"].map({
        1: f"Near (<= {NEAR_THRESHOLD}m)",
        0: f"Far  (>  {NEAR_THRESHOLD}m)",
    })
    print(overall.to_string(index=False))

    # RQ2: by crime type (weighted)
    print("\nRQ2: By Crime Type (weighted)")
    breakdown = pd.read_sql(f"""
        SELECT
            c.crime_type,
            s.near_station,
            COUNT(*) AS crime_count,
            (SELECT SUM(population) FROM lsoa_stats
             WHERE is_outlier = 0 AND is_london = 1 AND near_station = s.near_station) AS group_pop
        FROM crimes c
        JOIN lsoa_stats s ON c.lsoa = s.lsoa_code
        WHERE s.is_outlier = 0 AND s.is_london = 1 AND s.near_station IS NOT NULL
        GROUP BY c.crime_type, s.near_station
    """, conn)
    breakdown["rate"] = breakdown["crime_count"] * 1000.0 / breakdown["group_pop"] / YEARS

    pivot = breakdown.pivot(index="crime_type", columns="near_station", values="rate")
    pivot.columns = ["Far (>500m)", "Near (<=500m)"]
    pivot["diff"] = pivot["Near (<=500m)"] - pivot["Far (>500m)"]
    pivot["ratio"] = (pivot["Near (<=500m)"] / pivot["Far (>500m)"]).round(2)
    pivot["pct"] = ((pivot["ratio"] - 1) * 100).round(1).astype(str) + "%"
    pivot = pivot.sort_values("ratio", ascending=False)
    print(pivot.round(2).to_string())

    # RQ2: density bands (weighted)
    print("\nRQ2: Station density bands (weighted)")
    density = pd.read_sql(f"""
        SELECT
            CASE
                WHEN stations_within_1km = 0             THEN '0 stations'
                WHEN stations_within_1km BETWEEN 1 AND 3 THEN '1-3 stations'
                WHEN stations_within_1km BETWEEN 4 AND 7 THEN '4-7 stations'
                ELSE '8+ stations'
            END AS band,
            COUNT(*) AS n_lsoas,
            ROUND(SUM(total_crimes) * 1000.0 / SUM(population) / {YEARS}, 2) AS annual_rate_per_1k
        FROM lsoa_stats
        WHERE is_outlier = 0 AND is_london = 1 AND stations_within_1km IS NOT NULL
        GROUP BY band
        ORDER BY annual_rate_per_1k
    """, conn)
    print(density.to_string(index=False))

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()