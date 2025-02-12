import json
import datetime
import time
import threading
import traceback
from digi.xbee.devices import XBeeDevice, RemoteXBeeDevice
import config

# Global variables for the XBee device
device = None
xbee_ready = False

def open_xbee_device():
    global device, xbee_ready
    try:
        device = XBeeDevice(config.PORT, config.BAUD_RATE)
        device.open()
        xbee_ready = True
        print("XBee device opened and ready.")
        return True
    except Exception as e:
        xbee_ready = False
        print(f"Error opening XBee device: {e}")
        return False

def send_via_xbee(payload):
    global device, xbee_ready
    if not xbee_ready:
        # Fallback mechanism if XBee is not available
        print(f"XBee not available. Simulating send: {payload}")
        return
    
    try:
        boat_id = payload.get('id')
        payload_json = json.dumps(payload)
        with config.active_boats_lock:
            if boat_id in config.active_boats:
                remote_address = config.active_boats[boat_id]['address']
                remote_device = RemoteXBeeDevice(device, remote_address)
                device.send_data_async(remote_device, payload_json)
                print(f"Sent data to {boat_id}: {payload_json}")
            else:
                device.send_data_broadcast(payload_json)
                print(f"Boat {boat_id} not found, sent broadcast: {payload_json}")
    except Exception as e:
        print(f"Error sending via XBee: {e}")
        traceback.print_exc()

def xbee_dispatcher():
    print("XBee dispatcher thread started.")
    if not xbee_ready:
        print("XBee device not available. Running in simulation mode.")
    while True:
        try:
            if xbee_ready:
                xbee_message = device.read_data()
                if xbee_message:
                    config.incoming_queue.put(xbee_message)
            else:
                time.sleep(0.1)
                
            if not config.outgoing_queue.empty():
                payload = config.outgoing_queue.get()
                send_via_xbee(payload)
        except Exception as e:
            print(f"Error in xbee_dispatcher: {e}")
            traceback.print_exc()
            time.sleep(1)

def message_processor():
    print("Message processor thread started.")
    while True:
        try:
            xbee_message = config.incoming_queue.get()
            process_incoming_message(xbee_message)
        except Exception as e:
            print(f"Error in message_processor: {e}")
            traceback.print_exc()
            time.sleep(1)

def dt_requester():
    while True:
        try:
            with config.active_boats_lock:
                for boat_id in list(config.active_boats.keys()):
                    request_payload = {
                        "t": "data_req",
                        "id": boat_id
                    }
                    config.outgoing_queue.put(request_payload)
                    print(f"Requested data from boat {boat_id}")
            time.sleep(1)  # Request data every 1 second
        except Exception as e:
            print(f"Error in dt_requester: {e}")
            traceback.print_exc()

def process_incoming_message(xbee_message):
    try:
        if not xbee_ready:
            print("Incoming XBee message processing (simulation mode)")
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

def register_boat(boat_id, xbee_message):
    try:
        address = xbee_message.remote_device.get_64bit_addr()
        with config.active_boats_lock:
            config.active_boats[boat_id] = {
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
        with config.active_boats_lock:
            if boat_id not in config.active_boats:
                address = xbee_message.remote_device.get_64bit_addr()
                config.active_boats[boat_id] = {
                    'address': address,
                    'last_seen': time.time(),
                    'data': {},
                    'status': data.get('s', 'unknown'),
                    'notification': data.get('n', '')
                }
                print(f"Boat {boat_id} automatically registered via heartbeat.")
            else:
                config.active_boats[boat_id]['last_seen'] = time.time()
                config.active_boats[boat_id]['status'] = data.get('s', 'unknown')
                config.active_boats[boat_id]['notification'] = data.get('n', '')
                print(f"Heartbeat received from {boat_id} with status '{config.active_boats[boat_id]['status']}'")
    except Exception as e:
        print(f"Error in handle_heartbeat: {e}")
        traceback.print_exc()

def handle_dt_1(boat_id, data, xbee_message):
    try:
        with config.active_boats_lock:
            if boat_id not in config.active_boats:
                address = xbee_message.remote_device.get_64bit_addr()
                config.active_boats[boat_id] = {
                    'address': address,
                    'last_seen': time.time(),
                    'data': {}
                }
                print(f"Boat {boat_id} automatically registered via DT1.")
            
            config.active_boats[boat_id]['data'].update({
                'latitude': data.get('lt', 0.0),
                'longitude': data.get('lg', 0.0)
            })
            config.active_boats[boat_id]['last_seen'] = time.time()
            print(f"Received DT 1 data from {boat_id}: {data}")

        time_now = datetime.datetime.utcnow().isoformat()
        with config.app.app_context():
            config.socketio.emit('boat_data', {
                'boat_id': boat_id,
                'data': config.active_boats[boat_id]['data'],
                'timestamp': time_now
            })
    except Exception as e:
        print(f"Error in handle_dt_1: {e}")
        traceback.print_exc()

def handle_dt_2(boat_id, data, xbee_message):
    try:
        with config.active_boats_lock:
            if boat_id not in config.active_boats:
                address = xbee_message.remote_device.get_64bit_addr()
                config.active_boats[boat_id] = {
                    'address': address,
                    'last_seen': time.time(),
                    'data': {}
                }
                print(f"Boat {boat_id} automatically registered via DT2.")

            config.active_boats[boat_id]['data'].update({
                'wind_dir': data.get('w', 0.0),
                'temperature': data.get('tp', 0.0),
                'heading': data.get('h', 0.0)
            })
            config.active_boats[boat_id]['last_seen'] = time.time()
            print(f"Received DT 2 data from {boat_id}: {data}")

        time_now = datetime.datetime.utcnow().isoformat()
        with config.app.app_context():
            config.socketio.emit('boat_data', {
                'boat_id': boat_id,
                'data': config.active_boats[boat_id]['data'],
                'timestamp': time_now
            })
    except Exception as e:
        print(f"Error in handle_dt_2: {e}")
        traceback.print_exc()

def cleanup_inactive_boats():
    TIMEOUT = 6
    while True:
        try:
            current_time = time.time()
            with config.active_boats_lock:
                inactive_boats = [boat_id for boat_id, boat_info in config.active_boats.items()
                                  if current_time - boat_info['last_seen'] > TIMEOUT]
                for boat_id in inactive_boats:
                    print(f"Removing inactive boat: {boat_id}")
                    del config.active_boats[boat_id]
            time.sleep(TIMEOUT)
        except Exception as e:
            print(f"Error in cleanup_inactive_boats: {e}")
            traceback.print_exc()
            time.sleep(TIMEOUT)

def start_threads():
    threading.Thread(target=xbee_dispatcher, daemon=True).start()
    threading.Thread(target=message_processor, daemon=True).start()
    threading.Thread(target=dt_requester, daemon=True).start()

def start_periodic_tasks():
    threading.Thread(target=cleanup_inactive_boats, daemon=True).start()
