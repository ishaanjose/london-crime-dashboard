import sqlite3
import pandas as pd
import numpy as np
import requests
import time

DB_PATH = "street_crime.db"
NEAR_THRESHOLD_M = 500 # distance in meters to consider a station to be near
BATCH_SIZE = 50 # ArcGIs API limit per request
ARGIS_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BFE_V10/"
    "FeatureServer/0/query"
)

def haversine(lat1, lon1, lat2, lon2):
    """ Calculate distance in meters between two lat/lon points using the Haversine formula. """
    R = 6371000 # earth radius in meters
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def fetch_centroids(lsoa_codes):
    """ Fetch real LSOA centroid coordinates from ArcGIS API in batches"""
    all_rows = []
    batches = [lsoa_codes[i:i + BATCH_SIZE] for i in range(0, len(lsoa_codes), BATCH_SIZE)]
    print("Fetching centroids from ArcGIS API...")
    for i, batch in enumerate(batches):
        where = "LSOA21CD IN ('" + "','".join(batch) + "')"
        r = requests.get(ARGIS_URL, params={
            "where": where,
            "outFields": "LSOA21CD,LAT,LONG",
            "returnGeometry": "false",
            "f": "json"
        }, timeout=30)
        features = r.json().get("features", [])
        for feat in features:
            a = feat['attributes']
            all_rows.append({'lsoa_code': a['LSOA21CD'], 'lat': a['LAT'], 'lon': a['LONG']})
        if i%20 == 0:
            print(f"  Fetched {len(all_rows)} centroids so far...")
        time.sleep(0.1)
    return pd.DataFrame(all_rows)


def run():
    conn = sqlite3.connect(DB_PATH)

    lsoa_codes = pd.read_sql("SELECT lsoa_code FROM lsoa_stats", conn)['lsoa_code'].tolist()
    print(f"Total LSOAs to process: {len(lsoa_codes)}")

    stations = pd.read_sql("SELECT name, lat, lon FROM stations", conn) 
    print(f"Total stations: {len(stations)}")

    centroids = fetch_centroids(lsoa_codes)
    print(f"Total centroids fetched: {len(centroids)}")

    stations_lats = stations['lat'].values
    stations_lons = stations['lon'].values
    distances, nearest = [],[]

    for _, row in centroids.iterrows():
        dists = haversine(row['lat'], row['lon'], stations_lats, stations_lons)
        idx = np.argmin(dists)
        distances.append(dists[idx])
        nearest.append(stations.iloc[idx]['name'])


    centroids['distance_to_station_m'] = distances
    centroids['nearest_station'] = nearest
    centroids['near_station'] = (centroids['distance_to_station_m'] <= NEAR_THRESHOLD_M).astype(int)

    print("Updating database with proximity results...")
    for col in ['distance_to_station_m', 'nearest_station', 'near_station']:
        try:
            conn.execute(f"ALTER TABLE lsoa_stats ADD COLUMN {col}")
        except:
            pass
    
    centroids[['lsoa_code', 'distance_to_station_m', 'nearest_station', 'near_station']].to_sql(
        '_stn_tmp', conn, if_exists='replace', index=False)
    
    conn.execute("""
        UPDATE lsoa_stats SET
                 distance_to_station_m = (SELECT distance_to_station_m FROM _stn_tmp WHERE _stn_tmp.lsoa_code = lsoa_stats.lsoa_code),
                 nearest_station = (SELECT nearest_station FROM _stn_tmp WHERE _stn_tmp.lsoa_code = lsoa_stats.lsoa_code),
                 near_station = (SELECT near_station FROM _stn_tmp WHERE _stn_tmp.lsoa_code = lsoa_stats.lsoa_code)
    """)
    conn.execute("DROP TABLE _stn_tmp")
    conn.commit()
    print("Database update complete.")

    print('RQ2: Near vs Far station, overall crime rate')
    results = pd.read_sql("""
        SELECT near_station, COUNT(*) AS n_lsoas,
                          ROUND(AVG(annual_crime_rate_per_1000), 2) AS avg_rate
                          FROM lsoa_stats
                          WHERE is_outlier = 0 AND near_station IS NOT NULL
                            GROUP BY near_station
                          """, conn)
    results['near_station'] = results['near_station'].map({1: 'Near (<=500m)', 0: 'Far (>500m)'})
    print(results.to_string(index=False))

    print('rq2: near vs far by crime type')
    breakdown = pd.read_sql("""
        SELECT 
            types.crime_type, 
            s.near_station, 
            ROUND(AVG(COALESCE(c.type_count, 0) * 1000.0 / s.population), 2) AS avg_specific_rate
        FROM lsoa_stats s
        CROSS JOIN (SELECT DISTINCT crime_type FROM crimes) types
        LEFT JOIN (
            SELECT lsoa, crime_type, COUNT(*) as type_count 
            FROM crimes 
            GROUP BY lsoa, crime_type
        ) c ON c.lsoa = s.lsoa_code AND c.crime_type = types.crime_type
        WHERE s.is_outlier = 0 AND s.near_station IS NOT NULL
        GROUP BY types.crime_type, s.near_station
    """, conn)

    pivot = breakdown.pivot(index='crime_type', columns='near_station', values='avg_specific_rate').fillna(0)   
    pivot.columns = ['Far (>500m)', 'Near (<=500m)']
    pivot['diff'] = pivot['Near (<=500m)'] - pivot['Far (>500m)']
    pivot['pcf'] = pivot['diff'] / pivot['Far (>500m)'] * 100
    print(pivot.to_string())

    conn.close()


if __name__ == "__main__":
    run()