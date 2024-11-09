import json
import time
import threading
from flask import Flask
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress

# Flask application setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# XBee setup
PORT = "/dev/cu.usbserial-AG0JYY5U"  # Update to your XBee's port
BAUD_RATE = 115200
device = None

# Dictionary to track active boats
active_boats = {}  # Format: {'boat_id': {'address': XBee64BitAddress, 'last_seen': timestamp, 'location': {...}, 'data': {...}}}

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
        message_type = data.get('type')
        boat_id = data.get('boat_id')

        if message_type == 'registration':
            register_boat(boat_id, xbee_message)
        elif message_type == 'heartbeat':
            handle_heartbeat(boat_id, xbee_message)
        elif message_type == 'location_update':
            update_location(boat_id, data)
        elif message_type == 'data_transfer':
            handle_data_transfer(boat_id, data)
    except Exception as e:
        print(f"Error handling XBee data: {e}")

def register_boat(boat_id, xbee_message):
    """Register or update a boat's information."""
    active_boats[boat_id] = {
        'address': xbee_message.remote_device.get_64bit_addr(),
        'last_seen': time.time(),
        'location': {},
        'data': {}
    }
    print(f"Boat {boat_id} registered with address {active_boats[boat_id]['address']}")

def handle_heartbeat(boat_id, xbee_message):
    """Update last seen for the boat's heartbeat."""
    if boat_id in active_boats:
        active_boats[boat_id]['last_seen'] = time.time()
        print(f"Heartbeat received from {boat_id}")
    else:
        # Register the boat if it sent a heartbeat first
        register_boat(boat_id, xbee_message)
        print(f"Boat {boat_id} registered via heartbeat")

def update_location(boat_id, data):
    """Update boat location."""
    if boat_id in active_boats:
        active_boats[boat_id]['location'] = data['location']
        active_boats[boat_id]['last_seen'] = time.time()
        print(f"Updated location for {boat_id}: {data['location']}")

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
            "type": "data_request",
            "boat_id": boat_id
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

def request_data_from_active_boats():
    while True:
        current_time = time.time()
        for boat_id, boat_info in list(active_boats.items()):
            if current_time - boat_info['last_seen'] < 30:  # Boat is active
                send_data_request_to_boat(boat_id)
            else:
                print(f"Boat {boat_id} is inactive, skipping data request.")
        time.sleep(10)  # Wait 10 seconds before the next round

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
        boat_data = [
            {
                'boat_id': boat_id,
                'location': boat_info.get('location', {}),
                'status': 'active' if time.time() - boat_info['last_seen'] < 30 else 'inactive'
            }
            for boat_id, boat_info in active_boats.items()
        ]
        socketio.emit('boat_locations', boat_data)
        socketio.sleep(1)

# Start broadcasting locations in a background task
@socketio.on('connect')
def handle_connect():
    print("Frontend connected")
    emit('server_response', {'message': 'Connection established!'})
    socketio.start_background_task(broadcast_locations)

@socketio.on('gui_data')
def handle_gui_data(data):
    boat_id = data.get('boat_id')
    if not boat_id:
        print("No boat_id specified in the data.")
        return

    # Prepare payload to send to the specific boat
    payload = {
        "type": "command",
        "boat_id": boat_id,
        "command_mode": data.get('command_mode'),
        "target_lat": data.get('target_gps_latitude', 0),
        "target_lng": data.get('target_gps_longitude', 0),
        "rudder_angle": data.get('rudder_angle', 0),
        "sail_angle": data.get('sail_angle', 0),
        "throttle": data.get('throttle', 0)
    }
    send_command_to_boat(boat_id, payload)

def send_command_to_boat(boat_id, payload):
    """Send command to boat if available."""
    payload_json = json.dumps(payload)
    if xbee_ready and boat_id in active_boats:
        try:
            remote_address = active_boats[boat_id]['address']
            remote_device = RemoteXBeeDevice(device, remote_address)
            device.send_data_async(remote_device, payload_json)
            print(f"Sent command to {boat_id}: {payload_json}")
        except Exception as e:
            print(f"Error sending data to {boat_id}: {e}")
    else:
        print(f"XBee device not ready or boat {boat_id} not available")

@socketio.on('request_boat_list')
def handle_request_boat_list():
    boat_list = [
        {
            'boat_id': boat_id,
            'location': {
                'latitude': boat_info['location'].get('latitude', 37.86118),
                'longitude': boat_info['location'].get('longitude', -122.35204)
            }
        }
        for boat_id, boat_info in active_boats.items()
    ]
    socketio.emit('boat_locations', boat_list)
    print("Sent boat list to frontend.")

@socketio.on('disconnect')
def handle_disconnect():
    print("Frontend disconnected")

# Run the Flask-SocketIO server
if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=3336)
    finally:
        if device and device.is_open():
            device.close()
            print("XBee device closed.")
