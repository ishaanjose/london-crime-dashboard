import sqlite3
import pandas as pd
import os

DB_PATH = '../data/street_crime.db'
IMD_PATH = '../data/indices_of_deprivation.csv'
LOOKUP_PATH = '../data/lsoa11_to_lsoa21_lookup.csv' 


def integrate_imd():
    conn = sqlite3.connect(DB_PATH)

    for col in ['imd_rank INTEGER', 'imd_decile INTEGER']:
        try:
            conn.execute(f'ALTER TABLE crimes ADD COLUMN {col}')
        except sqlite3.OperationalError:
            pass

    
    try:
        crimes = pd.read_sql('SELECT rowid, lsoa FROM crimes', conn)
        imd = pd.read_csv(IMD_PATH)
        imd_map = imd[['LSOA code (2011)', 'Index of Multiple Deprivation (IMD) Rank', 'Index of Multiple Deprivation (IMD) Decile']]
        imd_map.columns = ['lsoa11', 'rank', 'decile']
    except Exception as e:
        print(f"Error reading data: {e}")
        return
    
    lookup = pd.read_csv(LOOKUP_PATH)
    lookup = lookup[['LSOA11CD', 'LSOA21CD']].drop_duplicates()


# Identify 2011 equivalents for records using 2021 codes
    crimes = crimes.merge(lookup, left_on='lsoa', right_on='LSOA21CD', how='left')
    crimes['target_lsoa11'] = crimes['LSOA11CD'].fillna(crimes['lsoa'])
    enriched_data = crimes.merge(imd_map, left_on='target_lsoa11', right_on='lsoa11', how='left')

    # Temp table
    enriched_data[['rowid', 'rank', 'decile']].to_sql('imd_sync', conn, if_exists='replace', index=False)
    conn.execute("""
        UPDATE crimes SET 
            imd_rank = s.rank, 
            imd_decile = s.decile
        FROM imd_sync s WHERE crimes.rowid = s.rowid
    """)
    conn.commit()
    conn.close()



if __name__ == "__main__":
    integrate_imd()
    print("IMD integration complete.")

