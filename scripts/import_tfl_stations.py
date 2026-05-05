import sqlite3

import geopandas as gpd

DB_PATH = "data/street_crime.db"
KML_PATH = "data/tfl_train_stations.kml"


def load_stations_from_kml():
    """Parse TFL stations KML and return GeoDataFrame.

    Extract name and point coordinates (lat/lon)
    """
    gdf = gpd.read_file(KML_PATH)

    name_col = None
    for candidate in ["name", "Name", "TITLE", "title"]:
        if candidate in gdf.columns:
            name_col = candidate
            break

    gdf = gdf[gdf.geometry.notnull()].copy()
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y

    core_cols = [name_col, "lat", "lon"]
    other_cols = [c for c in gdf.columns if c not in core_cols + ["geometry"]]
    gdf = gdf[core_cols + other_cols]

    if name_col != "name":
        gdf = gdf.rename(columns={name_col: "name"})

    return gdf


def write_stations_table():
    """Create/replace a `stations` table in the SQLite DB from the KML."""
    gdf = load_stations_from_kml()

    conn = sqlite3.connect(DB_PATH)
    try:
        gdf.to_sql("stations", conn, if_exists="replace", index=False)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS stations_with_id AS
            SELECT rowid AS station_id, * FROM stations;
            """
        )
        conn.commit()
        print(f"Imported {len(gdf)} stations into 'stations' table.")
    finally:
        conn.close()


if __name__ == "__main__":
    write_stations_table()
