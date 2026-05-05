"""
fetches London parks from OSM Overpass API and stores them in a `parks` table for the map.

"""
import sqlite3
import requests
import time

DB_PATH = "../data/street_crime.db"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "LondonCrimeDashboard/1.0"}

# Same bbox + query as park_proximity.py
QUERY = """
[out:json][timeout:60];
(
  node["leisure"="park"](51.28,-0.51,51.70,0.33);
  way["leisure"="park"](51.28,-0.51,51.70,0.33);
  relation["leisure"="park"](51.28,-0.51,51.70,0.33);
);
out center tags;
"""

def fetch_parks():
    print("Fetching parks from Overpass API...")
    r = requests.post(OVERPASS_URL, data={"data": QUERY}, headers=HEADERS, timeout=120)
    r.raise_for_status()
    elements = r.json().get("elements", [])
    print(f"  Got {len(elements)} elements from Overpass")

    parks = []
    for el in elements:
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        name = el.get("tags", {}).get("name", "Unnamed park")
        parks.append((name, lat, lon))
    return parks


def main():
    parks = fetch_parks()
    print(f"Storing {len(parks)} parks in DB...")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS parks")
    cur.execute("""
        CREATE TABLE parks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
    """)
    cur.executemany("INSERT INTO parks (name, lat, lon) VALUES (?, ?, ?)", parks)
    cur.execute("CREATE INDEX idx_parks_coords ON parks(lat, lon)")
    conn.commit()

    n = cur.execute("SELECT COUNT(*) FROM parks").fetchone()[0]
    print(f"Done. {n} parks stored in `parks` table.")
    conn.close()


if __name__ == "__main__":
    main()