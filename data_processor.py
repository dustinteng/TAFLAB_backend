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
