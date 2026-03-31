import requests, time

BASE = "http://127.0.0.1:8000"
TARGET = 750

endpoints = [
    "/boroughs",
    "/crime_types",
    "/summary?start_date=2025-01&end_date=2025-03",
    "/summary_by_borough?start_date=2025-01&end_date=2025-03",
    "/trends?start_date=2025-01&end_date=2025-03",
    "/imd_deciles",
    "/imd_scatter",
    "/seasonal",
    "/correlation_results",
]

print(f"{'Endpoint':<50} {'Time (ms)':>10} {'Result':>8}")
print("-" * 72)
for ep in endpoints:
    t = time.time()
    try:
        requests.get(f"{BASE}{ep}", timeout=300)
        ms = (time.time() - t) * 1000
        result = "PASS" if ms < TARGET else "FAIL"
        print(f"{ep:<50} {ms:>9.0f}ms {result:>8}")
    except Exception as e:
        print(f"{ep:<50} {'ERROR':>10} {'FAIL':>8}")
