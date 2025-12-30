import sqlite3
import geopandas
import pandas as pd
from shapely.geometry import Point
import time

DB_FILE = 'street_crime.db'
TABLE_NAME = 'crimes'
BOROUGH_BOUNDARIES = 'London Boroughs.geojson'

def enrich_db():
    """
    
    """

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        boroughs_gdf = geopandas.read_file(BOROUGH_BOUNDARIES)
        crimes = pd.read_sql_query(f"SELECT ROWID, latitude, longitude FROM {TABLE_NAME}", conn)

        # Convert crime data to GDF in order to then merge
        crime_points = [Point(xy) for xy in zip(crimes['longitude'], crimes['latitude'])]
        crime_gdf = geopandas.GeoDataFrame(crimes, geometry=crime_points, crs="EPSG:4326")

        # Perform sjoin. Calculate time. 

        start_time = time.time()
        joined_gdf = geopandas.sjoin(crime_gdf, boroughs_gdf, how="inner", predicate='within')
        end_time = time.time()
        print(f"SPATIAL JOIN DONE IN {end_time - start_time} seconds")

        print("Adding the 'borough' column to the database table...")
        cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN borough TEXT")
        conn.commit()

        # Add colomn to DB
        update_data = list(zip(joined_gdf['BOROUGH'], joined_gdf['rowid']))
        update_query = f"UPDATE {TABLE_NAME} SET borough = ? WHERE ROWID = ?"
        cursor.executemany(update_query,update_data)
        conn.commit()
        print('FINISHED')

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    enrich_db()
