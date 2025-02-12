import csv
import datetime
import os
import time
import config

# Ensure CSV directory exists
if not os.path.exists(config.CSV_DIR):
    os.makedirs(config.CSV_DIR)

def write_data_to_csv(data):
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(config.CSV_DIR, f"data_{timestamp}.csv")
    fieldnames = data[0].keys() if data else []
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
        with config.active_boats_lock:
            data_to_save = [
                {"boat_id": boat_id, **info["data"], "last_seen": info["last_seen"]}
                for boat_id, info in config.active_boats.items()
            ]
        if data_to_save:
            write_data_to_csv(data_to_save)
        time.sleep(300)  # 5 minutes
