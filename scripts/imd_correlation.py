import sqlite3
import pandas as pd
from scipy.stats import pearsonr

def calculate_normalized_correlations():
    """
    Calculates Pearson correlation between IMD Rank and Annualized Crime Rate.
    Filters out commercial/low-population outliers
    """
    conn = sqlite3.connect('data/street_crime.db')
    
    # Identify unique crime types
    crime_types = pd.read_sql("SELECT DISTINCT crime_type FROM crimes", conn)['crime_type'].tolist()
    
    # We append '-01' to the YYYY-MM strings for calculations which require full date
    span_query = "SELECT (julianday(MAX(month) || '-01') - julianday(MIN(month) || '-01')) / 365.25 as span FROM crimes"
    span_info = pd.read_sql(span_query, conn).iloc[0]
    
    raw_span = span_info['span']
    # If span is valid, use it, otherwise default to 1.0
    span_years = raw_span if pd.notnull(raw_span) and raw_span > 0 else 1.0

    results = []

    print(f"Dataset span: {span_years:.2f} years")
    print(f"{'Crime Type':<35} | {'Pearson r':<10} | {'P-Value':<10} | {'Strength'}")
    print("-" * 75)

    for c_type in crime_types:
        # Join crimes with lsoa_stats to calculate rate per specific crime type
        # Formula: ((Type Count / Span) / LSOA Population) * 1000
        query = f"""
            SELECT 
                s.lsoa_code, 
                AVG(c.imd_rank) as rank, 
                ((CAST(COUNT(*) AS FLOAT) / {span_years}) / s.population) * 1000 as annual_rate
            FROM crimes c
            JOIN lsoa_stats s ON c.lsoa = s.lsoa_code
            WHERE c.imd_rank IS NOT NULL 
              AND c.crime_type = '{c_type}'
              AND s.is_outlier = 0
            GROUP BY s.lsoa_code
        """
        df = pd.read_sql(query, conn)
        
        if len(df) < 30:
            continue

        r_coeff, p_value = pearsonr(df['rank'], df['annual_rate'])
        
        if p_value < 0.05:
            strength = "Weak"
            if abs(r_coeff) > 0.5: strength = "Strong"
            elif abs(r_coeff) > 0.3: strength = "Moderate"

            results.append({
                "type": c_type,
                "r": round(r_coeff, 4),
                "p": f"{p_value:.2e}",
                "strength": strength,
                "abs_r": abs(r_coeff)
            })

    sorted_results = sorted(results, key=lambda x: x['abs_r'], reverse=True)
    for res in sorted_results:
        print(f"{res['type']:<35} | {res['r']:>10} | {res['p']:>10} | {res['strength']}")

    conn.close()
    return sorted_results

def analyze_normalized_deciles():
    """
    Aggregates annualized crime rates by IMD Decile using lsoa_stats.
    Excludes outliers to show true residential socio-economic impact.
    """
    conn = sqlite3.connect('data/street_crime.db')
    
    print("\n--- Mean Annual Crime Rate by IMD Decile (Residential Only) ---")
    print(f"{'Decile':<10} | {'Avg Annual Rate/1000 Residents':<30}")
    
    # We join lsoa_stats with a unique map of LSOA to Decile
    query = """
        SELECT 
            t.imd_decile, 
            AVG(s.annual_crime_rate_per_1000) as avg_rate
        FROM lsoa_stats s
        JOIN (SELECT DISTINCT lsoa, imd_decile FROM crimes WHERE imd_decile IS NOT NULL) t 
          ON s.lsoa_code = t.lsoa
        WHERE s.is_outlier = 0
        GROUP BY t.imd_decile
        ORDER BY t.imd_decile ASC
    """
    
    df = pd.read_sql(query, conn)
    
    for _, row in df.iterrows():
        print(f"{int(row['imd_decile']):<10} | {row['avg_rate']:>30.2f}")
    
    conn.close()

if __name__ == "__main__":
    calculate_normalized_correlations()
    analyze_normalized_deciles()