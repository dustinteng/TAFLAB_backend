import json
import time
import threading
from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress
from flask import request  # Add this import at the top if not already present


# Flask application setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*",
                     engineio_logger=True, 
                     ping_interval=25,  # Ping every 25 seconds
                     ping_timeout=60    # Wait 60 seconds before timing out)
)

# XBee setup
PORT = "/dev/cu.usbserial-AG0JYY5U"  # Update to your XBee's port
BAUD_RATE = 115200
device = None

# Dictionary to track active boats
active_boats = {}  # Format: {'boat_id': {'address': XBee64BitAddress, 'last_seen': timestamp, 'data': {...}}}

# Dictionary to track client information
clients = {}

# Flag to ensure broadcast_locations is started only once
broadcast_thread_started = False

# Helper function to open XBee device
def open_xbee_device():
    global device
    try:
        device = XBeeDevice(PORT, BAUD_RATE)
        device.open()
        device.add_data_received_callback(xbee_data_receive_callback)
        print("XBee device opened and ready.")
        return True
    except Exception as e:
        print(f"Error opening XBee device: {e}")
        return False

# XBee data receive callback function
def xbee_data_receive_callback(xbee_message):
    global active_boats
    try:
        data = json.loads(xbee_message.data.decode())
        message_type = data.get('t')
        boat_id = data.get('id')

        if message_type == 'reg':
            register_boat(boat_id, xbee_message)
        elif message_type == 'hb':
            handle_heartbeat(boat_id, data, xbee_message)
        elif message_type == 'dt':
            handle_data_transfer(boat_id, data)
        else:
            print(f"Unknown message type '{message_type}' from boat '{boat_id}'")
    except Exception as e:
        print(f"Error handling XBee data: {e}")

def register_boat(boat_id, xbee_message):
    """Register or update a boat's information."""
    active_boats[boat_id] = {
        'address': xbee_message.remote_device.get_64bit_addr(),
        'last_seen': time.time(),
        'data': {}
    }
    print(f"Boat {boat_id} registered with address {active_boats[boat_id]['address']}")

def handle_heartbeat(boat_id, data, xbee_message):
    """Update last seen for the boat's heartbeat."""
    if boat_id in active_boats:
        active_boats[boat_id]['last_seen'] = time.time()
        active_boats[boat_id]['status'] = data.get('s', 'unknown')  # Store the status
        active_boats[boat_id]['notification'] = data.get('n', '')   # Store the notification
        print(f"Heartbeat received from {boat_id} with status '{active_boats[boat_id]['status']}'")
    else:
        # Register the boat if it sent a heartbeat first
        register_boat(boat_id, xbee_message)
        print(f"Boat {boat_id} registered via heartbeat")

def handle_data_transfer(boat_id, data):
    """Handle data_transfer messages from the boat."""
    if boat_id in active_boats:
        active_boats[boat_id]['data'] = data  # Store the data_transfer payload
        active_boats[boat_id]['last_seen'] = time.time()
        print(f"Received data_transfer from {boat_id}: {data}")
        # Emit data to the frontend
        socketio.emit('boat_data', {'boat_id': boat_id, 'data': data})
    else:
        print(f"Received data_transfer from unregistered boat {boat_id}")

def send_data_request_to_boat(boat_id):
    """Send a data request to a specific boat."""
    if boat_id in active_boats:
        payload = {
            "t": "dr",
            "id": boat_id
        }
        payload_json = json.dumps(payload)
        if xbee_ready:
            try:
                remote_address = active_boats[boat_id]['address']
                remote_device = RemoteXBeeDevice(device, remote_address)
                device.send_data_async(remote_device, payload_json)
                print(f"Sent data_request to {boat_id}")
            except Exception as e:
                print(f"Error sending data_request to {boat_id}: {e}")
        else:
            print(f"XBee device not ready, cannot send data_request to {boat_id}")
    else:
        print(f"Boat {boat_id} not found in active_boats")

active_boats_lock = threading.Lock()
def request_data_from_active_boats():
    while True:
        try:
            current_time = time.time()
            for boat_id, boat_info in list(active_boats.items()):
                if current_time - boat_info['last_seen'] < 30:  # Boat is active
                    send_data_request_to_boat(boat_id)
                else:
                    print(f"Boat {boat_id} is inactive, skipping data request.")
            time.sleep(10)  # Wait 10 seconds before the next round
        except Exception as e:
            print(f"Error in request_data_from_active_boats: {e}")
            time.sleep(10)  # Sleep before retrying to prevent rapid looping

# Start the data request loop in a background thread
threading.Thread(target=request_data_from_active_boats, daemon=True).start()

# Attempt to open XBee device
xbee_ready = open_xbee_device()

# Reconnect logic for XBee device
def xbee_reconnect():
    global xbee_ready
    while not xbee_ready:
        print("Attempting to reconnect to XBee device...")
        xbee_ready = open_xbee_device()
        time.sleep(5)  # Wait before retrying

# Start a background thread for XBee reconnection if necessary
if not xbee_ready:
    threading.Thread(target=xbee_reconnect, daemon=True).start()

# Cleanup thread to remove inactive boats
def cleanup_inactive_boats():
    TIMEOUT = 30  # seconds
    while True:
        current_time = time.time()
        for boat_id in list(active_boats.keys()):
            if current_time - active_boats[boat_id]['last_seen'] > TIMEOUT:
                print(f"Removing inactive boat: {boat_id}")
                del active_boats[boat_id]
        time.sleep(TIMEOUT)

# Start cleanup thread for inactive boats
threading.Thread(target=cleanup_inactive_boats, daemon=True).start()

# Function to broadcast boat locations to frontend
def broadcast_locations():
    while True:
        try:
            boat_data = []
            for boat_id, boat_info in active_boats.items():
                last_seen = boat_info.get('last_seen', 0)
                status = 'active' if time.time() - last_seen < 30 else 'inactive'
                data = boat_info.get('data', {})
                location = {
                    'latitude': data.get('lat', 0.0),
                    'longitude': data.get('lng', 0.0)
                }
                boat_data.append({
                    'boat_id': boat_id,
                    'location': location,
                    'status': status
                })
            socketio.emit('boat_locations', boat_data)
            socketio.sleep(1)
        except Exception as e:
            print(f"Error in broadcast_locations: {e}")
            socketio.sleep(1)


# Start the broadcast_locations loop in a background thread only once
def start_broadcast():
    global broadcast_thread_started
    if not broadcast_thread_started:
        broadcast_thread_started = True
        socketio.start_background_task(broadcast_locations)
        print("Started broadcast_locations background task.")

# Start the broadcast when the server starts
start_broadcast()

@socketio.on('connect')
def handle_connect():
    sid = request.sid  # Session ID for the connected client
    client_ip = request.remote_addr  # Client's IP address
    connect_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())

    # Store client information in the clients dictionary
    clients[sid] = {'ip': client_ip, 'connect_time': connect_time}
    print(f"Client connected: {sid} from IP {client_ip} at {connect_time}")


@socketio.on('request_boat_list')
def handle_request_boat_list():
    boat_list = []
    for boat_id, boat_info in active_boats.items():
        data = boat_info.get('data', {})
        location = {
            'latitude': data.get('lat', 37.86118),
            'longitude': data.get('lng', -122.35204)
        }
        boat_list.append({
            'boat_id': boat_id,
            'location': location
        })
    # Emit only to the requesting client
    emit('boat_locations', boat_list)
    print("Sent boat list to frontend.")

@socketio.on('gui_data')
def handle_gui_data(data):
    boat_id = data.get('boat_id')
    if not boat_id:
        print("No boat_id specified in the data.")
        return

    # Prepare payload to send to the specific boat
    payload = {
        "t": "cmd",
        "id": boat_id,
        "cmd": data.get('command_mode'),
        "tlat": data.get('target_gps_latitude', 0),
        "tlng": data.get('target_gps_longitude', 0),
        "r": data.get('r', 0),
        "s": data.get('s', 0),
        "th": data.get('th', 0)
    }
    send_command_to_boat(boat_id, payload)

def send_command_to_boat(boat_id, payload):
    """Send command to boat, defaulting to broadcast if unicast fails."""
    payload_json = json.dumps(payload)
    
    if not xbee_ready:
        print("XBee device not ready, cannot send command.")
        return

    try:
        if boat_id in active_boats:
            # Attempt to send via unicast to the specific boat
            remote_address = active_boats[boat_id]['address']
            remote_device = RemoteXBeeDevice(device, remote_address)
            device.send_data_async(remote_device, payload_json)
            print(f"Sent unicast command to {boat_id}: {payload_json}")
        else:
            # Fall back to broadcast if the boat is not in active_boats
            device.send_data_broadcast(payload_json)
            print(f"Boat {boat_id} not found in active_boats, sent broadcast command: {payload_json}")
    except Exception as e:
        print(f"Error sending command to {boat_id}: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid  # Get the session ID of the disconnecting client
    client_info = clients.pop(sid, None)  # Remove client data from the dictionary

    if client_info:
        print(f"Client disconnected: {sid} from IP {client_info['ip']} at {client_info['connect_time']}")
    else:
        print(f"Client disconnected: {sid} with no additional information.")


# Run the Flask-SocketIO server
if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=3336)
    finally:
        if device and device.is_open():
            device.close()
            print("XBee device closed.")
