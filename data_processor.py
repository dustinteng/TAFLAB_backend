import csv
import datetime
import os
import time
import requests
import pandas as pd
import json
from config import SERVER_IP
import config
import urllib.parse 

# Ensure CSV directory exists
if not os.path.exists(config.CSV_DIR):
    os.makedirs(config.CSV_DIR)

def write_data_to_csv(data):
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(config.CSV_DIR, f"{timestamp}_data.csv")
    # Determine fieldnames by combining all keys present in the data entries.
    if data:
        fieldnames = set()
        for row in data:
            fieldnames.update(row.keys())
        fieldnames = list(fieldnames)
    else:
        fieldnames = []
    try:
        with open(filename, mode="w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        print(f"Saved CSV: {filename}")
    except Exception as e:
        print(f"Error writing CSV: {e}")

def periodic_csv_writer():
    while True:
        # Wait for 5 minutes (300 seconds)
        time.sleep(60)
        with config.data_log_lock:
            if not config.data_log:
                print("No new data to write in the last 5 minutes.")
                continue
            # Copy and clear the global data log
            data_to_save = config.data_log.copy()
            config.data_log.clear()
        write_data_to_csv(data_to_save)



def get_all_tables():
    """Fetch all available tables from the database."""
    try:
        url = f"http://{SERVER_IP}/tables"  # Ensure this is correct
        print(f"Fetching tables from {url}")  # Debug step 1
        
        response = requests.get(url, timeout=10)
        print(f"Response status: {response.status_code}")  # Debug step 2
        print(f"Response text: {response.text}")  # Debug step 3
        
        if response.status_code == 200:
            tables = response.json()
            print(f"Tables received: {tables}")  # Debug step 4
            
            if not tables:
                return []
            return tables["tables"]  # Extract table names
        else:
            print(f"Failed to fetch tables: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching tables: {e}")
        return []


def fetch_boat_data(table_name):
    """Fetch boat data from a specific table in the database."""
    try:
        formatted_table_name = f'"{table_name.strip("\"")}"'  # Ensure quotes
        encoded_table_name = urllib.parse.quote(formatted_table_name, safe='')  # <-- Fix encoding
        url = f"http://{SERVER_IP}/table/{encoded_table_name}"  # Fetch data from database
        print(f"🔍 Fetching data from: {url}")  # Debugging
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            print(f"❌ Failed to fetch data from {table_name}: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return pd.DataFrame()
