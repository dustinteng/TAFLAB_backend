import threading
from queue import Queue

# XBee configuration
PORT = "/dev/cu.usbserial-AG0JYY5U"
BAUD_RATE = 115200

# CSV and uploader configuration
CSV_DIR = "csv_data"
UPLOAD_URL = "http://your-backend-server.com/api/upload_csv"  # Replace with your actual endpoint
CHECK_INTERVAL = 60  # seconds between connectivity checks

# Global data stores
active_boats = {}
active_boats_lock = threading.Lock()
calibration_settings = {}
calibration_lock = threading.Lock()
clients = {}
clients_lock = threading.Lock()

incoming_queue = Queue()
outgoing_queue = Queue()

# Placeholders for Flask and SocketIO instances (set in app.py)
app = None
socketio = None
