import threading
from queue import Queue

import json

# Load configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)



### XBee Configuration ###
PORT = "/dev/cu.usbserial-AG0JYY5U"  # Serial port for XBee module
BAUD_RATE = 115200  # Baud rate for XBee communication

### CSV and File Uploader Configuration ###
CSV_DIR = "csv_data"  # Directory for storing CSV files before upload
CSV_SENT_DIR = "csv_data_sent"  # Directory for successfully uploaded CSV files
CHECK_INTERVAL = 60  # Time interval (in seconds) to check for connectivity and new files

### Server API Configuration ###
SERVER_IP = config["SERVER_IP"]
TEST_URL = f"http://{SERVER_IP}/tables"  # API endpoint to check connectivity
UPLOAD_URL = f"http://{SERVER_IP}/upload"  # API endpoint to upload CSV files

### Global Data Stores ###
# Dictionary for active boats, with thread-safe access
active_boats = {}
active_boats_lock = threading.Lock()

# Dictionary for storing calibration settings, with thread-safe access
calibration_settings = {}
calibration_lock = threading.Lock()

# Dictionary for connected clients (e.g., GUI users), with thread-safe access
clients = {}
clients_lock = threading.Lock()

# Queues for handling incoming and outgoing messages asynchronously
incoming_queue = Queue()
outgoing_queue = Queue()

# Global log for data to be written to CSV, with thread-safe access
data_log = []
data_log_lock = threading.Lock()

# Placeholders for Flask and SocketIO instances (to be initialized in app.py)
app = None
socketio = None
