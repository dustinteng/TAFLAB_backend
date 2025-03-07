from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import config
from config import SERVER_IP
import data_processor
import threading
import uploader
import xbee_handler

# Initialize Flask
app = Flask(__name__)

# Enable CORS properly
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode='threading',
                    ping_interval=60,
                    ping_timeout=180)

config.app = app
config.socketio = socketio

@app.route("/get_available_tables", methods=["GET"])
def get_available_tables():
    """API route to list all tables"""
    tables = data_processor.get_all_tables()
    if not tables:
        return jsonify({"error": "No tables available"}), 404
    return jsonify(tables)

# Run Flask server
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)

from flask import Flask, jsonify, request
import data_processor
import urllib.parse

@app.route("/table/<path:table_name>", methods=["GET"])
def get_boat_data(table_name):
    """API route to serve boat data from a specific table."""
    print(f"🔍 Received request for table: {table_name}")  # DEBUG PRINT

    df = data_processor.fetch_boat_data(table_name)

    if df.empty:
        print(f"❌ No data found for table: {table_name}")  # DEBUG PRINT
        return jsonify({"error": "No data available"}), 404

    print(f"✅ Successfully fetched data for {table_name}")  # DEBUG PRINT
    return jsonify(df.to_dict(orient="records"))


# SocketIO Event Handlers

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    client_ip = request.remote_addr
    connect_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    with config.clients_lock:
        config.clients[sid] = {'ip': client_ip, 'connect_time': connect_time}
    print(f"Client connected: {sid} from IP {client_ip} at {connect_time}")

@socketio.on('request_boat_list')
def handle_request_boat_list():
    try:
        with config.active_boats_lock:
            boat_list = [{'boat_id': boat_id, 'data': info['data']} for boat_id, info in config.active_boats.items()]
        emit('boat_locations', boat_list)
        print("Sent boat list to frontend.")
        print(f"Boats connected: {len(boat_list)}")
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

        config.outgoing_queue.put(payload)
    except Exception as e:
        print(f"Error in handle_gui_data: {e}")
        traceback.print_exc()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    with config.clients_lock:
        client_info = config.clients.pop(sid, None)
    if client_info:
        print(f"Client disconnected: {sid} from IP {client_info['ip']}")

@socketio.on('request_calibration_data')
def handle_request_calibration_data(data):
    boat_id = data.get('id')
    request_payload = {"t": "req_cal_data", "id": boat_id}
    config.outgoing_queue.put(request_payload)
    print(f"Sent calibration data request to boat {boat_id}")

    calibration_response_event = threading.Event()

    def calibration_response_listener(response_data):
        if response_data.get('id') == boat_id and response_data.get('t') == "cal_data":
            socketio.emit('calibration_data_response', {'id': boat_id, 'data': response_data})
            calibration_response_event.set()

    socketio.on_event('calibration_data_response', calibration_response_listener)

    if not calibration_response_event.wait(timeout=5):
        socketio.emit('calibration_data_response', {
            'id': boat_id,
            'error': 'Calibration data not received from boat'
        })
    else:
        print(f"Calibration data for {boat_id} successfully received and sent to frontend")

@socketio.on('calibration_data')
def handle_calibration_data(data):
    try:
        print(f"Received calibration data: {data}")
        print(f"Data type: {type(data)}")

        if isinstance(data, dict):
            if 'id' in data:
                boat_id = data.get('id')
                with config.calibration_lock:
                    config.calibration_settings[boat_id] = data
                print(f"Calibration data for {boat_id} saved: {data}")
                
                payload = {
                    "t": "cal",
                    "id": boat_id,
                    "rm": round(data.get("rudderMin"), 1),
                    "rx": round(data.get("rudderMax"), 1),
                    "sm": round(data.get("sailMin"), 1),
                    "sx": round(data.get("sailMax"), 1),
                    "em": round(data.get("throttleMin"), 1),
                    "ex": round(data.get("throttleMax"), 1)
                }
                if isinstance(payload, dict):
                    xbee_handler.send_via_xbee(payload)
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
        config.outgoing_queue.put(payload)
        print(f"Testing calibration for {boat_id} - {value_type}: {value}")
    except Exception as e:
        print(f"Error in handle_test_calibration: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    try:
        # Open the XBee device
        xbee_handler.open_xbee_device()
        # Start XBee-related threads and periodic tasks
        xbee_handler.start_threads()
        xbee_handler.start_periodic_tasks()
        # Start the CSV writer thread
        threading.Thread(target=data_processor.periodic_csv_writer, daemon=True).start()
        # Start the uploader thread
        threading.Thread(target=uploader.upload_csv_files, daemon=True).start()
        # Run the Flask-SocketIO server
        socketio.run(app, host='0.0.0.0', port=5001, debug=True)
    finally:
        if xbee_handler.device and xbee_handler.device.is_open():
            xbee_handler.device.close()
            print("XBee device closed.")
