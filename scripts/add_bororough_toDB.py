import sqlite3
import geopandas
import pandas as pd
from shapely.geometry import Point
import time

DB_FILE = 'data/street_crime.db'
TABLE_NAME = 'crimes'
BOROUGH_BOUNDARIES = 'data/London Boroughs.geojson'

def enrich_db():
    """Connect to crime database and assign borough names using spatial join.

    Reads the crime table from SQLite, converts the latitude/longitude 
coordinates into points, and joins them with a GeoDataFrame of London borough
    boundaries. 
    
    borough value is then written back into the database for each crime record.
    """

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Load London borough boundaries from a GeoJSON file.
        boroughs_gdf = geopandas.read_file(BOROUGH_BOUNDARIES)

        crimes = pd.read_sql_query(f"SELECT ROWID, latitude, longitude FROM {TABLE_NAME}", conn)

        # Convert each crime location into a shapely Point and build a GeoDataFrame
        crime_points = [Point(xy) for xy in zip(crimes['longitude'], crimes['latitude'])]
        crime_gdf = geopandas.GeoDataFrame(crimes, geometry=crime_points, crs="EPSG:4326")

        # Use a spatial join to find which borough contains each crime point
        start_time = time.time()
        joined_gdf = geopandas.sjoin(crime_gdf, boroughs_gdf, how="inner", predicate='within')
        end_time = time.time()
        print(f"Spatial join completed in {end_time - start_time:.2f} seconds")

        # Add a new borough column to the crimes table 
        print("Adding the 'borough' column to the database table...")
        cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN borough TEXT")
        conn.commit()

        # Prepare update data and apply borough names for each matching row.
        update_data = list(zip(joined_gdf['BOROUGH'], joined_gdf['rowid']))
        update_query = f"UPDATE {TABLE_NAME} SET borough = ? WHERE ROWID = ?"
        cursor.executemany(update_query,update_data)
        conn.commit()
        print('Finished enriching the database with borough information')

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    enrich_db()
