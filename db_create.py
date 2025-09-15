import sqlite3
import pandas as pd
import glob



# Function to concatenate all CSV files from MET download. Saves to all_data.csv
def concat_csvs(directory):
    files = glob.glob(directory + '/**/*.csv', recursive=True)
    pd.concat([pd.read_csv(f) for f in files]).to_csv('all_data.csv', index=False)




con = sqlite3.connect('street_crime.db')
cur = con.cursor()
cur.execute('''CREATE TABLE crimes (month text, longitude int, latitude int, crime_type text, lsoa text )''')

all_data = pd.read_csv('all_data.csv')

all_data = all_data.rename(columns={all_data.columns[1]: 'month', all_data.columns[4]: 'longitude', all_data.columns[5]: 'latitude', all_data.columns[9]: 'crime_type', all_data.columns[7]: 'lsoa'})
all_data.to_csv('all_data2.csv')



crimes = pd.read_csv('all_data2.csv', usecols=['month','longitude','latitude','crime_type', 'lsoa'])
crimes.to_sql('crimes', con, if_exists='append',index=False)
 

# DELETE FROM crimes WHERE longitude IS NULL OR latitude IS NULL;