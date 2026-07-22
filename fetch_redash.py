#!/usr/bin/env python3
"""
Fetches the latest results of Redash query 127151 and writes sales_data.csv.
Run before update_dashboard.py in the auto-update workflow.
"""
import csv
import os
import sys
import urllib.request
import json

QUERY_ID = 127151
REDASH_URL = "https://dash.prod.bi.auto1.team"
API_KEY = os.environ.get("REDASH_API_KEY")

if not API_KEY:
    sys.exit("REDASH_API_KEY environment variable is not set.")

req = urllib.request.Request(
    f"{REDASH_URL}/api/queries/{QUERY_ID}/results.json",
    headers={"Authorization": f"Key {API_KEY}"},
)
with urllib.request.urlopen(req, timeout=120) as resp:
    payload = json.load(resp)

rows = payload["query_result"]["data"]["rows"]
columns = [c["name"] for c in payload["query_result"]["data"]["columns"]]

if not rows:
    sys.exit("Redash query 127151 returned no rows.")

with open("sales_data.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote sales_data.csv with {len(rows):,} rows.")
