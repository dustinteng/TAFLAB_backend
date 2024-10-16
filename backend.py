from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS  # Import CORS
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice, XBee64BitAddress
import json
import threading
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS to allow requests from any origin
socketio = SocketIO(app, cors_allowed_origins="*")  # Allow WebSocket connections from any origin

# XBee setup
PORT = "/dev/cu.usbserial-AG0JYY5U"   # Update this to your XBee's port (e.g., '/dev/ttyUSB0' on Linux)
BAUD_RATE = 115200
REMOTE_NODE_ID = "DRONE_PI"
device = None
remote_device = None

def open_xbee_device():
    global device, remote_device
    try:
        device = XBeeDevice(PORT, BAUD_RATE)
        device.open()
        xbee_network = device.get_network()

        # Discover the remote device by Node ID
        remote_device = xbee_network.discover_device(REMOTE_NODE_ID)
        if remote_device is None:
            print("Could not find the remote device with Node ID '{}'".format(REMOTE_NODE_ID))
            # Alternatively, create a RemoteXBeeDevice with known address
            # remote_device = RemoteXBeeDevice(device, XBee64BitAddress.from_hex_string("0013A200XXXXXXXX"))
            return False
        else:
            print("Remote device found: {}".format(remote_device))
            return True
    except Exception as e:
        print("Error opening XBee device: {}".format(e))
        return False

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

@socketio.on('gui_data')
def handle_gui_data(data):
    global device, remote_device, xbee_ready
    # Handle the data coming from the frontend
    print(f"Received data from GUI: {data}")

    try:
        # Parse the data and include command_mode
        command_mode = data.get('command_mode', 'manual')
        payload = data  # Use the entire data object as the payload

        # Prepare the payload as a JSON string to send over XBee
        payload_json = json.dumps(payload)

        # Send the payload to the remote XBee device
        if xbee_ready and remote_device is not None:
            try:
                device.send_data_async(remote_device, payload_json)
                print(f"Sent data to remote device: {payload_json}")
            except Exception as e:
                print(f"Error sending data: {e}")
                xbee_ready = False  # Set to False to trigger reconnection
        else:
            print("XBee device not ready or remote device not available")
    except Exception as e:
        print(f"Error handling data: {e}")

if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=3336)
    finally:
        # Close the XBee device when the application exits
        if device is not None and device.is_open():
            device.close()
            print("XBee device closed.")
