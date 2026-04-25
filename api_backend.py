import sqlite3
import pandas as pd
import geopandas
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from shapely.geometry import Point
import numpy as np

DB_FILE = 'street_crime.db'
TABLE_NAME = 'crimes'
BOROUGH_BOUNDARIES_FILE = 'London Boroughs.geojson'

imd_scatter_cache = None

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
    global imd_scatter_cache

    # Return cached result if we've already computed it
    if imd_scatter_cache is not None:
        return imd_scatter_cache

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

    # Normalized annual crime rate per 1000 residents for each LSOA
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

    imd_scatter_cache = scatter_data
    return imd_scatter_cache


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


# /correlation_results
# Returns Pearson r between IMD rank and annual crime rate per 1000 residents foor each crime type, across non-outlier LSOAs.
# Negative r means more deprived (lower rank) = higher crime rate.

correlation_cache = None  # cached after first run 
@app.get("/correlation_results")
def get_correlation_results():
    """
    Pearson correlation between IMD rank and annualised crime rate per 1000
    residents, broken down by crime type.
    Only returns results where p < 0.05 and n >= 30 LSOAs.
    Sorted by absolute r value descending (strongest first).
    """
    global correlation_cache
    if correlation_cache is not None:
        return correlation_cache

    from scipy.stats import pearsonr

    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    try:
        # How many years does the dataset span? annualise crime counts.
        span_df = pd.read_sql(
            "SELECT (julianday(MAX(month) || '-01') - julianday(MIN(month) || '-01')) / 365.25 AS span FROM crimes",
            conn
        )
        span_years = float(span_df.iloc[0]["span"])
        if span_years <= 0:
            span_years = 1.0

        crime_types = pd.read_sql(
            "SELECT DISTINCT crime_type FROM crimes ORDER BY crime_type", conn
        )["crime_type"].tolist()

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Setup query failed: {e}")

    results = []

    for c_type in crime_types:
        try:
            # Per-LSOA: average IMD rank + annualised crime rate for this crime type.
            # is_outlier = 0 excludes commercial/industrial LSOAs with tiny population that would skew the residential correlation.
            query = f"""
                SELECT
                    s.lsoa_code,
                    AVG(c.imd_rank) AS imd_rank,
                    ((CAST(COUNT(*) AS FLOAT) / {span_years}) / s.population) * 1000 AS annual_rate
                FROM crimes c
                JOIN lsoa_stats s ON c.lsoa = s.lsoa_code
                WHERE c.imd_rank IS NOT NULL
                  AND c.crime_type = ?
                  AND s.is_outlier = 0
                GROUP BY s.lsoa_code
            """
            df = pd.read_sql(query, conn, params=(c_type,))
        except Exception:
            continue

        # Need at least 30 data points for a meaningful correlation
        if len(df) < 30:
            continue

        r_val, p_val = pearsonr(df["imd_rank"], df["annual_rate"])

        # Drop non-significant results
        if p_val >= 0.05:
            continue

        abs_r = abs(r_val)
        strength = "Weak"
        if abs_r > 0.5:
            strength = "Strong"
        elif abs_r > 0.3:
            strength = "Moderate"

        results.append({
            "crime_type": c_type,
            "pearson_r": round(r_val, 4),
            "p_value": round(p_val, 10),
            "strength": strength,
            "n_lsoas": int(len(df)),
        })

    conn.close()

    # Strongest correlation first
    results.sort(key=lambda x: abs(x["pearson_r"]), reverse=True)

    correlation_cache = results
    return correlation_cache



## Seasonal EP
# Groups crimes by month (Jan, Feb, etc) across all years, to identify seasonal patterns.
@app.get("/seasonal")
def get_seasonal():
    """
    Returns average monthly crime count per season per crime type.
    Seasons: Spring (Mar-May), Summer (Jun-Aug), Autumn (Sep-Nov), Winter (Dec-Feb).
    """
    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    try:
        monthly = pd.read_sql("""
            SELECT crime_type, month, COUNT(*) as crime_count
            FROM crimes
            GROUP BY crime_type, month""", conn)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error querying seasonal data: {e}")
    
    conn.close()

    season_map = {
        '01': 'Winter', '02': 'Winter', '12': 'Winter',
        '03': 'Spring', '04': 'Spring', '05': 'Spring',
        '06': 'Summer', '07': 'Summer', '08': 'Summer',
        '09': 'Autumn', '10': 'Autumn', '11': 'Autumn',
    }
    monthly['month_num'] = monthly['month'].str[5:7]
    monthly['season'] = monthly['month_num'].map(season_map)

    result = (
        monthly.groupby(['crime_type', 'season'])['crime_count']
        .mean()
        .reset_index()
        .rename(columns={'crime_count': 'avg_monthly_count'})
    )
    
    result['avg_monthly_count'] = result['avg_monthly_count'].round(1)

    return result.to_dict(orient='records')



@app.get("/station_map_data")
def get_station_map_data():
    """
    For each TFL station, returns average annual crime rate per 1000 residents in nearby LSOAs, and distance to nearest station.
    """

    conn = db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    try: # Get all non-outlier LSOAs with their centroid coords + crime rates
        lsoas = pd.read_sql("""
            SELECT s.lsoa_code, s.annual_crime_rate_per_1000, AVG(c.latitude) as lat, AVG(c.longitude) as lon
            FROM lsoa_stats s 
            JOIN crimes c ON c.lsoa = s.lsoa_code
            WHERE s.is_outlier = 0 AND s.near_station IS NOT NULL AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
            GROUP BY s.lsoa_code
        """, conn)

        stations = pd.read_sql("""SELECT name, lat, lon FROM stations""", conn)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error querying station map data: {e}")
    
    conn.close()

    def haversine_vec(lat1, lon1, lat2, lon2):
        R = 6371000  
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1))*np.cos(np.radians(lat2))*np.sin(dlon/2)**2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    

    results = []
    for _, st in stations.iterrows():
        dists = haversine_vec(lsoas.lat.values, lsoas.lon.values, st.lat, st.lon)
        within = lsoas[dists <= 500]
        avg = round(float(within.annual_crime_rate_per_1000.mean()), 2) if not within.empty else 0
        results.append({
            "name"  : st["name"],
            "lat"   : st.lat,
            "lon"   : st.lon,
            "avg_rate_500": avg,
            "n_lsoas": int(len(within))
        })
    return results