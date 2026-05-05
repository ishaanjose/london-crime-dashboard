# Interactive Dashboard: London Street Crime Analysis

Student: Ishaan Jose Cortijo Matin  
Supervisor: Dr. Fabrizio Smeraldi  
Course: BSc Computer Science, QMUL  

## 1. Project Overview

This project analyzes 3.4 million crime records from the Metropolitan Police Service (2022–2025). It uses a decoupled three tier architecture to study how environmental factors like TfL stations, parks, and deprivation correlate with crime.

## 2. Directory Structure

• api/api_backend.py: The FastAPI logic layer handling data aggregation and caching.  
• app/app.py: The Python Dash frontend for interactive mapping and charts.  
• data/: Contains the SQLite database (street_crime.db), ONS deprivation data, and GeoJSON boundaries.  
• scripts/: All preprocessing scripts for spatial joins, IMD enrichment, and population normalization.  
• tests/: Performance benchmarking scripts.  


## 4. Setup and Execution

1. Install Dependencies:  
   `pip install -r requirements.txt`

2. Start the Backend API:  
   Navigate to the project root and run:  
   `uvicorn api.api_backend:app --reload --port 8000`

3. Start the Dashboard:  
   In a new terminal, run:  
   `python app/app.py`

4. Access:  
   Open http://127.0.0.1:8050 in your web browser.