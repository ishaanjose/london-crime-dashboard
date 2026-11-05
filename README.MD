# Interactive Dashboard: London Street Crime Analysis

Student: Ishaan Jose Cortijo Matin  
Supervisor: Dr. Fabrizio Smeraldi  
Course: BSc Computer Science, QMUL  

## 1. Project Overview

This project analyses 3.4 million crime records from the Metropolitan Police Service and City of London Police (2022–2025). It uses a decoupled three tier architecture to study how environmental factors like TfL stations, parks, and deprivation correlate with crime.

## 2. Directory Structure

• api/api_backend.py: The FastAPI logic layer handling data aggregation and caching.  
• app/app.py: The Python Dash frontend for interactive mapping and charts.  
• data/: Not in the repo, it's too big for git (see step 1 below). Holds the SQLite database (street_crime.db), ONS deprivation data, and GeoJSON boundaries.  
• scripts/: All preprocessing scripts for spatial joins, IMD enrichment, and population normalization.  
• tests/: Performance benchmarking scripts.  

## 3. Performance

3.4 million rows is too much to send to a browser, so most of the work happens on the server. Analytics endpoints that don't depend on the filters are computed once and cached in memory, which took /seasonal from around 7.8s to near instant. On the frontend, Dash's dcc.Store keeps fetched data in the browser so switching between the map and charts doesn't send new requests. 13 of the 15 endpoints respond in under 750ms (tests/benchmark.py).

## 4. Setup and Execution

1. Get the Data:  
   Download `data.zip` from the [Releases](https://github.com/ishaanjose/london-crime-dashboard/releases) page and unzip it into a `data/` folder in the project root.

2. Install Dependencies:  
   `pip install -r requirements.txt`

3. Start the Backend API:  
   Navigate to the project root and run:  
   `uvicorn api.api_backend:app --reload --port 8000`

4. Start the Dashboard:  
   In a new terminal, run:  
   `python app/app.py`

5. Access:  
   Open http://127.0.0.1:8050 in your web browser.
