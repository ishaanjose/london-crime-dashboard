import sqlite3
import pandas as pd
import geopandas
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from shapely.geometry import Point

DB_FILE = 'street_crime.db'
TABLE_NAME = 'crimes'
BOROUGH_BOUNDARIES_FILE = 'London Boroughs.geojson'

app = FastAPI(
    title='London Crime Data API',
    description='An API to query street-level crime data in London',
    version = '2.0.0',
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This line says "I allow requests from ANY origin"
    allow_credentials=True,
    allow_methods=["*"],  # Allows any method (GET, POST, etc.)
    allow_headers=["*"],  # Allows any headers
)

try:
    boroughs_gdf = geopandas.read_file(BOROUGH_BOUNDARIES_FILE)
    print("Successfully loaded borough boundaries GeoJSON.")
except Exception as e:
    print(f"CRITICAL ERROR: Could not load borough boundaries file: {e}")
    boroughs_gdf = None

def db_connection():
    try:
        conn = sqlite3.connect(DB_FILE)
    except sqlite3.Error as e:
        print(e)
        return None
    return conn

@app.get('/')
def read_root():
    return {"message": "Welcome to the Crime Data API v2! Use /docs to see endpoints."}



@app.get("/month_crimes")
def get_month_crimes(
    date: str,
    crime_type: Optional[str]=None,
):
    """
    Get crime data for a specific month.
    - date: The month to fetch data for (e.g., '2025-01').
    """

    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    query = f"SELECT latitude, longitude, crime_type, month FROM {TABLE_NAME} WHERE month = ?"
    params = [date]

    if crime_type:
        query += f'AND crime_type = ?'
        params.append(crime_type)



    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Convert the DataFrame to a dictionary before returning.
    return df.to_dict('records')

@app.get("/monthrange_crimes")
def get_range_crimes(
    start_d: str,
    end_d: str,
    crime_type: Optional[str]=None,

):
    """
    Get crime data within a specific month range.
    - start_d: The start month of the range
    - end_d: The end month of the range
    """
    
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    query = f"SELECT latitude, longitude, crime_type, month FROM {TABLE_NAME} WHERE month>=? AND month<= ?"
    params = [start_d,end_d]

    if crime_type:
        query += f'AND crime_type = ?'
        params.append(crime_type)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    return df.to_dict('records')

@app.get('/crime_types')
def get_types():
    """
    Get the different types of crimes.
    """

    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    query = f"SELECT DISTINCT crime_type FROM {TABLE_NAME}"

    df = pd.read_sql_query(query,conn)
    conn.close()

    return df.to_dict('records')

