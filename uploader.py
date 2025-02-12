import os
import time
import requests
import config

def is_internet_available():
    try:
        response = requests.get(config.UPLOAD_URL, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def upload_csv_files():
    while True:
        if is_internet_available():
            print("Internet is available. Checking for CSV files to upload...")
            for file in os.listdir(config.CSV_DIR):
                if file.endswith(".csv"):
                    file_path = os.path.join(config.CSV_DIR, file)
                    try:
                        with open(file_path, "rb") as f:
                            files = {"file": (file, f, "text/csv")}
                            response = requests.post(config.UPLOAD_URL, files=files, timeout=10)
                        if response.status_code == 200:
                            print(f"Uploaded {file} successfully. Removing local file.")
                            os.remove(file_path)
                        else:
                            print(f"Failed to upload {file}. Status: {response.status_code}")
                    except Exception as e:
                        print(f"Error uploading {file}: {e}")
        else:
            print("Internet not available. Will check again later.")
        time.sleep(config.CHECK_INTERVAL)
