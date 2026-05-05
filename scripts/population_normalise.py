import sqlite3
import pandas as pd
import os


DB_PATH = '../data/street_crime.db'
POPULATION_PATH = '../data/lsoa_population_estimates.xlsx'

def normalise_crime_by_population():
    """
    Normalises crime counts by population estimates for each LSOA.
    """

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS lsoa_stats (
            lsoa_code TEXT PRIMARY KEY,
            population INTEGER,
            total_crimes INTEGER,
            annual_crime_rate_per_1000 REAL,
            is_outlier INTEGER DEFAULT 0
        )
    """)

    try:
        pop_df = pd.read_excel(POPULATION_PATH, sheet_name='Mid-2022 LSOA 2021', skiprows=3)
        pop_df = pop_df[['LSOA 2021 Code', 'Total']]
        pop_df.columns = ['lsoa_code', 'population']
        pop_df = pop_df.dropna(subset=['lsoa_code'])


        #divide by the number of years to get an annual rate
        date_info = pd.read_sql("SELECT MIN(month) as start, MAX(month) as end FROM crimes", conn).iloc[0]
        start_date = pd.to_datetime(date_info['start'])
        end_date = pd.to_datetime(date_info['end'])

        span_years = (end_date - start_date).days / 365.25
        if span_years <= 0:
            span_years = 1.0


    except Exception as e:
        print(f"Error reading population data: {e}")
        return
    
    crime_counts = pd.read_sql("""SELECT lsoa as lsoa_code , COUNT(*) as total_crimes
                               FROM crimes
                                 GROUP BY lsoa
                               """, conn)
    

    # Join crime volumes with populations, get crime rate per 1000 residents
    stats= crime_counts.merge(pop_df, on='lsoa_code', how='inner')
    stats['annual_crime_rate_per_1000'] = ((stats['total_crimes'] / span_years) / stats['population']) * 1000
    rate_99th_percentile = stats['annual_crime_rate_per_1000'].quantile(0.99)
    stats['is_outlier'] = 0
    stats.loc[stats['population'] < 500, 'is_outlier'] = 1
    stats.loc[stats['annual_crime_rate_per_1000'] > rate_99th_percentile, 'is_outlier'] = 1

    stats.to_sql('lsoa_stats', conn, if_exists='replace', index=False)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_lsoa_stats_code ON lsoa_stats(lsoa_code)")
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    normalise_crime_by_population()