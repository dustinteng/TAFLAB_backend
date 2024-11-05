import json
import time
import threading
import uuid
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
active_boats = {}  # Format: {'boat_name': {'address': XBee64BitAddress, 'last_seen': timestamp, 'location': {...}}}

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
        boat_name = data.get('boat_name')

        if message_type == 'registration':
            # Register or update the boat's info
            active_boats[boat_name] = {
                'address': xbee_message.remote_device.get_64bit_addr(),
                'last_seen': time.time(),
                'location': data.get('location', {})  # Location if available
            }
            print(f"Boat {boat_name} registered with address {active_boats[boat_name]['address']}")

        elif message_type == 'heartbeat':
            # Update last seen for the boat's heartbeat
            if boat_name in active_boats:
                active_boats[boat_name]['last_seen'] = time.time()
                print(f"Heartbeat received from {boat_name}")
            else:
                # Register the boat if it sent a heartbeat first
                active_boats[boat_name] = {
                    'address': xbee_message.remote_device.get_64bit_addr(),
                    'last_seen': time.time(),
                    'location': data.get('location', {})
                }
                print(f"Boat {boat_name} registered via heartbeat")

        elif message_type == 'location_update':
            # Update boat location if available
            if boat_name in active_boats:
                active_boats[boat_name]['location'] = data['location']
                active_boats[boat_name]['last_seen'] = time.time()
                print(f"Updated location for {boat_name}: {data['location']}")

    except Exception as e:
        print(f"Error handling XBee data: {e}")

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
        for boat_name in list(active_boats.keys()):
            if current_time - active_boats[boat_name]['last_seen'] > TIMEOUT:
                print(f"Removing inactive boat: {boat_name}")
                del active_boats[boat_name]
        time.sleep(TIMEOUT)

# Start cleanup thread for inactive boats
threading.Thread(target=cleanup_inactive_boats, daemon=True).start()

# Function to broadcast boat locations to frontend
def broadcast_locations():
    while True:
        boat_data = []
        for boat_name, boat_info in active_boats.items():
            location = boat_info.get('location', {})
            boat_data.append({
                'boat_id': boat_name,
                'location': location,
                'status': 'active' if time.time() - boat_info['last_seen'] < 30 else 'inactive'
            })

        # Emit boat locations to frontend
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
    boat_name = data.get('boat_name')
    command_mode = data.get('command_mode')
    target_lat = data.get('target_gps_latitude') if data.get('target_gps_latitude') is not None else 0
    target_lng = data.get('target_gps_longitude') if data.get('target_gps_longitude') is not None else 0

    if not boat_name:
        print("No boat_name specified in the data.")
        return

    # Prepare payload to send to the specific boat
    payload = {
        "type": "command",
        "boat_name": boat_name,
        "command_mode": command_mode,
        "target_lat": target_lat,
        "target_lng": target_lng,
        "rudder_angle": data.get('rudder_angle', 0),
        "sail_angle": data.get('sail_angle', 0),
        "throttle": data.get('throttle', 0)
    }
    payload_json = json.dumps(payload)

    # Send command via XBee if the boat is registered and available
    if xbee_ready and boat_name in active_boats:
        try:
            remote_address = active_boats[boat_name]['address']
            remote_device = RemoteXBeeDevice(device, remote_address)
            device.send_data_async(remote_device, payload_json)
            print(f"Sent command to {boat_name}: {payload_json}")
        except Exception as e:
            print(f"Error sending data to {boat_name}: {e}")
    else:
        print(f"XBee device not ready or boat {boat_name} not available")

@socketio.on('request_boat_list')
def handle_request_boat_list():
    boat_list = []
    for boat_name, boat_info in active_boats.items():
        location = boat_info.get('location', {})
        boat_entry = {
            'boat_id': boat_name,
            'location': {
                'latitude': location.get('latitude', 37.86118),
                'longitude': location.get('longitude', -122.35204)
            }
        }
        boat_list.append(boat_entry)
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
