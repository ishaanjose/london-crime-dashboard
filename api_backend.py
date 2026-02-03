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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
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


@app.get("/crimes")
def get_crimes(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    specific_month: Optional[str] = None,
    crime_type: Optional[str] = None,
    borough: Optional[str] = None,

):
    """
    Get crime data, filtered by an optional date range, crime type, and borough.
    - To query a single month, set start_date and end_date to the same value (e.g., '2025-01').
    """
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    conn.row_factory = sqlite3.Row

    query = f"SELECT latitude, longitude, crime_type, month, borough FROM {TABLE_NAME}"
    where_clauses = []
    params = []

    if start_date:
        where_clauses.append("month >= ?")
        params.append(start_date)
    
    if end_date:
        where_clauses.append("month <= ?")
        params.append(end_date)

    if specific_month:
        where_clauses.append("month = ?")
        params.append(specific_month)

    if crime_type:
        where_clauses.append("crime_type = ?")
        params.append(crime_type)

    if borough:
        where_clauses.append("borough = ?")
        params.append(borough)

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    


    cursor = conn.cursor()
    cursor.execute(query, tuple(params))
    results = cursor.fetchall()
    conn.close()
    
    return results


@app.get('/boroughs')
def get_borough_list():
    """
    Gets the list of available London boroughs from the database.
    """
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    query = f"SELECT DISTINCT borough FROM {TABLE_NAME} WHERE borough IS NOT NULL ORDER BY borough"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # FIX: Return a dictionary, not a list
    return {"boroughs": df['borough'].tolist()}


@app.get("/summary")
def get_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    crime_type: Optional[str] = None,
    borough: Optional[str] = None,
):
    """
    Get a summary of crime data, including total crimes and a breakdown by type.
    """
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    conn.row_factory = sqlite3.Row

    where_clauses = []
    params = []

    if start_date:
        where_clauses.append("month >= ?")
        params.append(start_date)
    
    if end_date:
        where_clauses.append("month <= ?")
        params.append(end_date)

    if crime_type:
        where_clauses.append("crime_type = ?")
        params.append(crime_type)

    if borough:
        where_clauses.append("borough = ?")
        params.append(borough)

    where_query_part = ""
    if where_clauses:
        where_query_part = " WHERE " + " AND ".join(where_clauses)
    
    cursor = conn.cursor()

    total_count_query = f"SELECT COUNT(*) FROM {TABLE_NAME}" + where_query_part
    cursor.execute(total_count_query, tuple(params))
    total_crimes = cursor.fetchone()[0]

    crime_counts_by_type = {}
    
    if not crime_type:
        breakdown_query = f"SELECT crime_type, COUNT(*) as count FROM {TABLE_NAME}" + where_query_part + " GROUP BY crime_type ORDER BY count DESC"
        cursor.execute(breakdown_query, tuple(params))
        rows = cursor.fetchall()
        crime_counts_by_type = {row['crime_type']: row['count'] for row in rows}

    conn.close()
    
    return {
        "total_crimes": total_crimes,
        "crime_counts_by_type": crime_counts_by_type
    }


@app.get('/summary_by_borough')
def get_summary_by_borough(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    crime_type: Optional[str] = None,
    borough: Optional[str] = None,
):
    """
    Get crime counts grouped by borough for cholorpleth mapping.
    """
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    conn.row_factory = sqlite3.Row

    where_clauses = []
    params = []

    if start_date:
        where_clauses.append("month >= ?")
        params.append(start_date)
    
    if end_date:
        where_clauses.append("month <= ?")
        params.append(end_date)
    
    if crime_type:
        where_clauses.append("crime_type = ?")
        params.append(crime_type)

    if borough:
        where_clauses.append("borough = ?")
        params.append(borough)

    where_query_part = ""
    if where_clauses:
        where_query_part = " WHERE " + " AND ".join(where_clauses)


    # Ensure we only count records with a valid borough
    if where_query_part:
        where_query_part += " AND borough IS NOT NULL"
    else:
        where_query_part += " WHERE borough IS NOT NULL"

    cursor = conn.cursor()

    query = f"SELECT borough, COUNT(*) as count FROM {TABLE_NAME}" + where_query_part + " GROUP BY borough ORDER BY count DESC"
    cursor.execute(query, tuple(params))
    results = cursor.fetchall()
    conn.close()

    # Return as a list of dictionaries
    return [{'borough': row['borough'], 'count': row['count']} for row in results]
@app.get("/trends")
def get_trends(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    crime_type: Optional[str] = None,
    borough: Optional[str] = None,
    breakdown_by_type: bool = False
):
    """
    Get a time-series trend of crime counts.
    - Set breakdown_by_type=true to get counts for each crime type.
    """
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    conn.row_factory = sqlite3.Row

    where_clauses = []
    params = []

    if start_date:
        where_clauses.append("month >= ?")
        params.append(start_date)
    
    if end_date:
        where_clauses.append("month <= ?")
        params.append(end_date)

    if crime_type:
        where_clauses.append("crime_type = ?")
        params.append(crime_type)

    if borough:
        where_clauses.append("borough = ?")
        params.append(borough)

    where_query_part = ""
    if where_clauses:
        where_query_part = " WHERE " + " AND ".join(where_clauses)
    
    cursor = conn.cursor()

    if not breakdown_by_type:
        query = f"SELECT month, COUNT(*) as count FROM {TABLE_NAME}" + where_query_part + " GROUP BY month ORDER BY month"
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
    else:
        query = f"SELECT month, crime_type, COUNT(*) as count FROM {TABLE_NAME}" + where_query_part + " GROUP BY month, crime_type ORDER BY month, crime_type"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        trends_by_type = {}
        for row in rows:
            trends_by_type.setdefault(row['crime_type'], []).append({
                "month": row['month'],
                "count": row['count']
            })
        results = trends_by_type

    conn.close()
    return results



@app.get('/crime_types')
def get_types():
    """
    Get the different types of crimes.
    """
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    query = f"SELECT DISTINCT crime_type FROM {TABLE_NAME} ORDER BY crime_type"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return {"crime_types": df['crime_type'].tolist()}


@app.get("/imd_scatter")
def get_imd_scatter():
    """Return IMD vs annualised crime rate per 1000 residents at LSOA level.
    """

    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        span_query = "SELECT (julianday(MAX(month) || '-01') - julianday(MIN(month) || '-01')) / 365.25 as span FROM crimes"
        cursor.execute(span_query)
        row = cursor.fetchone()
        raw_span = row["span"] if row and row["span"] is not None else None
        span_years = raw_span if raw_span and raw_span > 0 else 1.0
    except Exception:
        span_years = 1.0

    #  normalized annual crime rate per 1000 residents for each LSOA
    try:
        query = f"""
            SELECT 
                s.lsoa_code,
                c.borough,
                AVG(c.imd_rank) as imd_rank,
                AVG(c.imd_decile) as imd_decile,
                ((CAST(COUNT(*) AS FLOAT) / {span_years}) / s.population) * 1000 as annual_rate_per_1000
            FROM crimes c
            JOIN lsoa_stats s ON c.lsoa = s.lsoa_code
            WHERE c.imd_rank IS NOT NULL
              AND s.population >= 500
              AND c.borough IS NOT NULL
            GROUP BY s.lsoa_code, c.borough
        """
        cursor.execute(query)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error querying IMD scatter data: {e}")

    conn.close()

    scatter_data = []
    for r in rows:
        if r["imd_rank"] is None or r["annual_rate_per_1000"] is None:
            continue
        scatter_data.append({
            "lsoa_code": r["lsoa_code"],
            "borough": r["borough"],
            "imd_rank": r["imd_rank"],
            "imd_decile": r["imd_decile"],
            "annual_rate_per_1000": r["annual_rate_per_1000"],
        })

    return scatter_data


@app.get("/imd_deciles")
def get_imd_deciles():
    """Return mean annual crime rate per 1000 residents by IMD decile.
    """

    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        query = """
            SELECT 
                t.imd_decile AS decile,
                AVG(s.annual_crime_rate_per_1000) AS avg_rate
            FROM lsoa_stats s
            JOIN (
                SELECT DISTINCT lsoa, imd_decile 
                FROM crimes 
                WHERE imd_decile IS NOT NULL
            ) t ON s.lsoa_code = t.lsoa
            GROUP BY t.imd_decile
            ORDER BY t.imd_decile ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error querying IMD decile data: {e}")

    conn.close()

    deciles = []
    for r in rows:
        if r["decile"] is None or r["avg_rate"] is None:
            continue
        deciles.append({
            "imd_decile": int(r["decile"]),
            "avg_rate": r["avg_rate"],
        })

    return deciles