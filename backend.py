from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress
import json
import threading
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# XBee setup
PORT = "/dev/cu.usbserial-AG0JYY5U"   # Update this to your XBee's port
BAUD_RATE = 115200
device = None

# Dictionary to hold active boats
active_boats = {}  # Key: boat_name, Value: {'address': XBee64BitAddress, 'last_seen': timestamp}

def open_xbee_device():
    global device
    try:
        device = XBeeDevice(PORT, BAUD_RATE)
        device.open()

        # Set up to receive data from boats
        device.add_data_received_callback(xbee_data_receive_callback)

        print("XBee device opened and ready.")
        return True
    except Exception as e:
        print("Error opening XBee device: {}".format(e))
        return False

def xbee_data_receive_callback(xbee_message):
    global active_boats
    try:
        data = json.loads(xbee_message.data.decode())
        message_type = data.get('type')
        boat_name = data.get('boat_name')

        if message_type == 'registration':
            # Existing registration logic
            active_boats[boat_name] = {
                'address': xbee_message.remote_device.get_64bit_addr(),
                'last_seen': time.time(),
                'location': data.get('location', {})  # Initialize location
            }
            print(f"Boat {boat_name} registered with address {active_boats[boat_name]['address']}")

        elif message_type == 'heartbeat':
            # Existing heartbeat logic
            if boat_name in active_boats:
                active_boats[boat_name]['last_seen'] = time.time()
                print(f"Heartbeat received from {boat_name}")
            else:
                # Boat might have restarted; re-register it
                active_boats[boat_name] = {
                    'address': xbee_message.remote_device.get_64bit_addr(),
                    'last_seen': time.time(),
                    'location': data.get('location', {})  # Initialize location
                }
                print(f"Boat {boat_name} re-registered via heartbeat.")

        elif message_type == 'location_update':
            # Update the boat's location
            if boat_name in active_boats:
                active_boats[boat_name]['location'] = data['location']
                active_boats[boat_name]['last_seen'] = time.time()
                print(f"Updated location for {boat_name}: {data['location']}")
            else:
                print(f"Received location update from unknown boat {boat_name}")
                # Optionally, register the boat
                active_boats[boat_name] = {
                    'address': xbee_message.remote_device.get_64bit_addr(),
                    'last_seen': time.time(),
                    'location': data['location']
                }

        else:
            print(f"Received unknown message type from {boat_name}: {message_type}")

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

# Start a background thread to handle XBee reconnection if necessary
if not xbee_ready:
    threading.Thread(target=xbee_reconnect, daemon=True).start()

# Cleanup thread to remove inactive boats
def cleanup_inactive_boats():
    global active_boats
    TIMEOUT = 30  # seconds
    while True:
        current_time = time.time()
        for boat_name in list(active_boats.keys()):
            if current_time - active_boats[boat_name]['last_seen'] > TIMEOUT:
                print(f"Removing inactive boat: {boat_name}")
                del active_boats[boat_name]
        time.sleep(TIMEOUT)

threading.Thread(target=cleanup_inactive_boats, daemon=True).start()

@socketio.on('gui_data')
def handle_gui_data(data):
    global device, active_boats, xbee_ready
    # Handle the data coming from the frontend
    print(f"Received data from GUI: {data}")

    try:
        # Extract the boat name from the data
        boat_name = data.get('boat_name')
        if not boat_name:
            print("No boat_name specified in the data.")
            return

        # Prepare the payload as a JSON string to send over XBee
        payload = {
            "type": "command",
            "boat_name": boat_name,
            "command_mode": data.get('command_mode', 'manual'),
            "rudder_angle": data.get('rudder_angle', 0),
            "sail_angle": data.get('sail_angle', 0),
            "throttle": data.get('throttle', 0),
            # Include other command data as needed
        }
        payload_json = json.dumps(payload)

        # Send the payload to the specific boat
        if xbee_ready and boat_name in active_boats:
            try:
                remote_address = active_boats[boat_name]['address']
                remote_device = RemoteXBeeDevice(device, XBee64BitAddress.from_hex_string(str(remote_address)))
                device.send_data_async(remote_device, payload_json)
                print(f"Sent data to {boat_name}: {payload_json}")
            except Exception as e:
                print(f"Error sending data to {boat_name}: {e}")
        else:
            print(f"XBee device not ready or boat {boat_name} not available")
    except Exception as e:
        print(f"Error handling data: {e}")


@socketio.on('request_boat_list')
def handle_request_boat_list():
    global active_boats
    boat_list = []
    for boat_name, boat_info in active_boats.items():
        # Check if latitude and longitude are available; set defaults if not
        location = boat_info.get('location', {})
        latitude = location.get('latitude', 37.86118)
        longitude = location.get('longitude', -122.35204)
        
        boat_entry = {
            'boat_id': boat_name,
            'location': {
                'latitude': latitude,
                'longitude': longitude
            }
        }
        boat_list.append(boat_entry)
    socketio.emit('boat_locations', boat_list)
    print("Sent boat list to frontend.")




if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=3336)
    finally:
        # Close the XBee device when the application exits
        if device is not None and device.is_open():
            device.close()
            print("XBee device closed.")
