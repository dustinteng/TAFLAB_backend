import json
import datetime
import time
import threading
from threading import Lock
from queue import Queue
from flask import Flask, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice
import traceback
import os


# Flask application setup
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode='threading',
                    ping_interval=60,
                    ping_timeout=180)

# XBee setup
PORT = "/dev/cu.usbserial-AG0JYY5U"
BAUD_RATE = 115200
device = None
xbee_ready = False

# Dictionaries to track active boats, clients, and calibration settings
active_boats = {}
active_boats_lock = Lock()
calibration_settings = {}
calibration_lock = Lock()
clients = {}
clients_lock = Lock()

# Message Queues
incoming_queue = Queue()
outgoing_queue = Queue()

# Helper function to open XBee device
def open_xbee_device():
    global device, xbee_ready
    try:
        device = XBeeDevice(PORT, BAUD_RATE)
        device.open()
        xbee_ready = True
        print("XBee device opened and ready.")
        return True
    except Exception as e:
        xbee_ready = False
        print(f"Error opening XBee device: {e}")
        return False

# THREAD - XBee Dispatcher Thead with fallback
def xbee_dispatcher():
    print("XBee dispatcher thread started.")
    if not xbee_ready:
        print("XBee device not available. Running in simulation mode.")
    while True:
        try:
            if xbee_ready:
                xbee_message = device.read_data()
                if xbee_message:
                    incoming_queue.put(xbee_message)
            else:
                time.sleep(0.1)
                
            if not outgoing_queue.empty():
                payload = outgoing_queue.get()
                send_via_xbee(payload)
        except Exception as e:
            print(f"Error in xbee_dispatcher: {e}")
            traceback.print_exc()
            time.sleep(1)

# Function to send data via XBee
def send_via_xbee(payload):
    if not xbee_ready:
        # Fallback mechanism if XBee is not available
        print(f"XBee not available. Simulating send: {payload}")
        return
    
    try:
        boat_id = payload.get('id')
        payload_json = json.dumps(payload)
        with active_boats_lock:
            if boat_id in active_boats:
                remote_address = active_boats[boat_id]['address']
                remote_device = RemoteXBeeDevice(device, remote_address)
                device.send_data_async(remote_device, payload_json)
                print(f"Sent data to {boat_id}: {payload_json}")
            else:
                device.send_data_broadcast(payload_json)
                print(f"Boat {boat_id} not found, sent broadcast: {payload_json}")
    except Exception as e:
        print(f"Error sending via XBee: {e}")
        traceback.print_exc()



# THREAD - Message Processor
def message_processor():
    print("Message processor thread started.")
    while True:
        try:
            xbee_message = incoming_queue.get()
            process_incoming_message(xbee_message)
        except Exception as e:
            print(f"Error in message_processor: {e}")
            traceback.print_exc()
            time.sleep(1)


# Thread to request data from boats periodically
def dt_requester():
    while True:
        try:
            with active_boats_lock:
                for boat_id in active_boats.keys():
                    request_payload = {
                        "t": "data_req",
                        "id": boat_id  # Request specific boat to send data
                    }
                    outgoing_queue.put(request_payload)
                    print(f"Requested data from boat {boat_id}")
            time.sleep(2)  # Request data every 2 seconds
        except Exception as e:
            print(f"Error in dt_requester: {e}")
            traceback.print_exc()


# Function to process incoming XBee messages
def process_incoming_message(xbee_message):
    try:
        if not xbee_ready:
            print("Simulating incoming XBee message processing")
            return  # Simulate behavior without processing
        data = json.loads(xbee_message.data.decode())
        message_type = data.get('t')
        boat_id = data.get('id')

        if message_type == 'reg':
            register_boat(boat_id, xbee_message)
        elif message_type == 'hb':
            handle_heartbeat(boat_id, data, xbee_message)
        elif message_type == 'dt1':
            handle_dt_1(boat_id, data, xbee_message)
        elif message_type == 'dt2':
            handle_dt_2(boat_id, data, xbee_message)
        else:
            print(f"Unknown message type '{message_type}' from boat '{boat_id}'")
    except Exception as e:
        print(f"Error processing incoming message: {e}")
        traceback.print_exc()

# data transfer 
def register_boat(boat_id, xbee_message):
    try:
        address = xbee_message.remote_device.get_64bit_addr()
        with active_boats_lock:
            active_boats[boat_id] = {
                'address': address,
                'last_seen': time.time(),
                'data': {}
            }
        print(f"Boat {boat_id} registered with address {address}")
    except Exception as e:
        print(f"Error in register_boat: {e}")
        traceback.print_exc()

def handle_heartbeat(boat_id, data, xbee_message):
    try:
        with active_boats_lock:
            if boat_id not in active_boats:
                address = xbee_message.remote_device.get_64bit_addr()
                active_boats[boat_id] = {
                    'address': address,
                    'last_seen': time.time(),
                    'data': {},
                    'status': data.get('s', 'unknown'),
                    'notification': data.get('n', '')
                }
                print(f"Boat {boat_id} automatically registered via heartbeat.")
            else:
                active_boats[boat_id]['last_seen'] = time.time()
                active_boats[boat_id]['status'] = data.get('s', 'unknown')
                active_boats[boat_id]['notification'] = data.get('n', '')
                print(f"Heartbeat received from {boat_id} with status '{active_boats[boat_id]['status']}'")
    except Exception as e:
        print(f"Error in handle_heartbeat: {e}")
        traceback.print_exc()

def handle_dt_1(boat_id, data, xbee_message):
    try:
        with active_boats_lock:
            if boat_id not in active_boats:
                address = xbee_message.remote_device.get_64bit_addr()
                active_boats[boat_id] = {
                    'address': address,
                    'last_seen': time.time(),
                    'data': {}
                }
                print(f"Boat {boat_id} automatically registered via DT1.")
            
            active_boats[boat_id]['data'].update({
                'latitude': data.get('lt', 0.0),
                'longitude': data.get('lg', 0.0)
            })
            active_boats[boat_id]['last_seen'] = time.time()
            print(f"Received DT 1 data from {boat_id}: {data}")

        # Add timestamp here
        time_now = datetime.datetime.utcnow().isoformat()

        with app.app_context():
            socketio.emit('boat_data', {
                'boat_id': boat_id,
                'data': active_boats[boat_id]['data'],
                'timestamp': time_now  # Include timestamp
            })
    except Exception as e:
        print(f"Error in handle_dt_1: {e}")
        traceback.print_exc()


def handle_dt_2(boat_id, data, xbee_message):
    try:
        with active_boats_lock:
            if boat_id not in active_boats:
                address = xbee_message.remote_device.get_64bit_addr()
                active_boats[boat_id] = {
                    'address': address,
                    'last_seen': time.time(),
                    'data': {}
                }
                print(f"Boat {boat_id} automatically registered via DT2.")

            active_boats[boat_id]['data'].update({
                'wind_dir': data.get('w', 0.0),
                'temperature': data.get('tp', 0.0),
                'heading': data.get('h',0.0)
            })
            active_boats[boat_id]['last_seen'] = time.time()
            print(f"Received magnetic field data from {boat_id}: {data}")

        # Add timestamp here
        time_now = datetime.datetime.utcnow().isoformat()
        with app.app_context():
            socketio.emit('boat_data', {
                'boat_id': boat_id,
                'data': active_boats[boat_id]['data'],
                'timestamp': time_now  # Include timestamp
            })
    except Exception as e:
        print(f"Error in handle_dt_2: {e}")
        traceback.print_exc()


# Periodic cleanup of inactive boats
def cleanup_inactive_boats():
    TIMEOUT = 10
    while True:
        try:
            current_time = time.time()
            with active_boats_lock:
                inactive_boats = [boat_id for boat_id, boat_info in active_boats.items()
                                  if current_time - boat_info['last_seen'] > TIMEOUT]
                for boat_id in inactive_boats:
                    print(f"Removing inactive boat: {boat_id}")
                    del active_boats[boat_id]
            time.sleep(TIMEOUT)
        except Exception as e:
            print(f"Error in cleanup_inactive_boats: {e}")
            traceback.print_exc()
            time.sleep(TIMEOUT)

# Start dispatcher and message processor threads
def start_threads():
    threading.Thread(target=xbee_dispatcher, daemon=True).start()
    threading.Thread(target=message_processor, daemon=True).start()
    # threading.Thread(target=dt_requester, daemon=True).start()  # Start the data requester thread


# Start periodic cleanup task
def start_periodic_tasks():
    threading.Thread(target=cleanup_inactive_boats, daemon=True).start()



# Flask-SocketIO Event Handlers
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    client_ip = request.remote_addr
    connect_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    with clients_lock:
        clients[sid] = {'ip': client_ip, 'connect_time': connect_time}
    print(f"Client connected: {sid} from IP {client_ip} at {connect_time}")

@socketio.on('request_boat_list')
def handle_request_boat_list():
    try:
        with active_boats_lock:
            boat_list = [{'boat_id': boat_id, 'data': info['data']} for boat_id, info in active_boats.items()]
        emit('boat_locations', boat_list)
        print("Sent boat list to frontend.")
        print(f"boats connected: {len(boat_list)}")
    except Exception as e:
        print(f"Error in handle_request_boat_list: {e}")
        traceback.print_exc()

@socketio.on('gui_data')
def handle_gui_data(data):
    try:
        boat_id = data.get('id')
        if not boat_id:
            print("No boat_id specified in the data.")
            return

        mode = data.get('md')
        payload = {
            "t": "cmd",
            "id": boat_id,
            "md": mode,
        }

        if mode == 'mnl':
            payload.update({"r": data.get('r', 0), "s": data.get('s', 0), "th": data.get('th', 0)})
        elif mode == 'auto':
            payload.update({"tlat": data.get('tlat', 0), "tlng": data.get('tlng', 0)})
        else:
            print("Invalid mode specified.")
            return

        outgoing_queue.put(payload)
    except Exception as e:
        print(f"Error in handle_gui_data: {e}")
        traceback.print_exc()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    with clients_lock:
        client_info = clients.pop(sid, None)
    if client_info:
        print(f"Client disconnected: {sid} from IP {client_info['ip']}")

@socketio.on('request_calibration_data')
def handle_request_calibration_data(data):
    boat_id = data.get('id')
    
    # Send request to the robot
    request_payload = {"t": "req_cal_data", "id": boat_id}
    outgoing_queue.put(request_payload)  # Add to outgoing XBee queue

    print(f"Sent calibration data request to boat {boat_id}")

    # Use a temporary dictionary to hold calibration responses until received
    calibration_response_event = threading.Event()

    def calibration_response_listener(response_data):
        if response_data.get('id') == boat_id and response_data.get('t') == "cal_data":
            socketio.emit('calibration_data_response', {'id': boat_id, 'data': response_data})
            calibration_response_event.set()  # Signal that data is received

    # Wait for the response
    socketio.on_event('calibration_data_response', calibration_response_listener)
    
    # Wait for up to 5 seconds for response from the boat
    if not calibration_response_event.wait(timeout=5):
        # If timeout, send error response back to frontend
        socketio.emit('calibration_data_response', {
            'id': boat_id,
            'error': 'Calibration data not received from boat'
        })
    else:
        print(f"Calibration data for {boat_id} successfully received and sent to frontend")

# NEED FIX SOON
@socketio.on('calibration_data')
def handle_calibration_data(data):
    try:
        # Debugging output to understand the incoming data structure
        print(f"Received calibration data: {data}")
        print(f"Data type: {type(data)}")

        # Verify that data is a dictionary and contains necessary fields
        if isinstance(data, dict):
            if 'id' in data:
                boat_id = data.get('id')
                
                # Assuming calibration_lock is defined and used to synchronize access to calibration settings
                with calibration_lock:
                    calibration_settings[boat_id] = data
                print(f"Calibration data for {boat_id} saved: {data}")
                
                # Add XBee-specific structure if needed
                payload = {
                    "t": "cal",             # Type shortened from "cal_data" to "cal"
                    "id": boat_id,          # Boat ID remains the same
                    "rm": round(data.get("rudderMin"), 1),  # Rudder min, rounded to 1 decimal
                    "rx": round(data.get("rudderMax"), 1),  # Rudder max, rounded to 1 decimal
                    "sm": round(data.get("sailMin"), 1),    # Sail min, rounded to 1 decimal
                    "sx": round(data.get("sailMax"), 1),    # Sail max, rounded to 1 decimal
                    "em": round(data.get("throttleMin"), 1),     # ESC min, rounded to 1 decimal
                    "ex": round(data.get("throttleMax"), 1)      # ESC max, rounded to 1 decimal
                }   

                # Check if payload is a dictionary before sending
                if isinstance(payload, dict):
                    send_via_xbee(payload)  # Call send_via_xbee with structured payload
            else:
                print("Data does not contain 'id' key.")
        else:
            print("Data is not a dictionary.")
    except Exception as e:
        print(f"Error in handle_calibration_data: {e}")
        traceback.print_exc()

@socketio.on('test_calibration')
def handle_test_calibration(data):
    try:
        boat_id = data.get('id')
        value_type = data.get('type')
        value = data.get('value')
        payload = {"t": "cal_test", "id": boat_id, value_type: value}
        outgoing_queue.put(payload)
        print(f"Testing calibration for {boat_id} - {value_type}: {value}")
    except Exception as e:
        print(f"Error in handle_test_calibration: {e}")
        traceback.print_exc()


# Run the server
if __name__ == '__main__':
    try:
        xbee_ready = open_xbee_device()
        start_threads()
        start_periodic_tasks()
        socketio.run(app, host='0.0.0.0', port=3336)
    finally:
        if device and device.is_open():
            device.close()
            print("XBee device closed.")
