import gevent.monkey
gevent.monkey.patch_all()
import gevent
import threading

from flask import Flask
from flask_socketio import SocketIO, emit
import random

# Create a Flask application
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Base coordinates near the target location
BASE_LAT = 37.866942
BASE_LON = -122.315452

# Generate a slightly random location around the base coordinates
def generate_location():
    return {
        "latitude": BASE_LAT + random.uniform(-0.002, 0.002),
        "longitude": BASE_LON + random.uniform(-0.002, 0.002)
    }

# thread1 = threading.Thread(target=broadcast_locations)

# Handle a new WebSocket connection
@socketio.on('connect')
def handle_connect():
    print('Frontend connected')
    socketio.start_background_task(broadcast_locations)
    # thread1.start()
    # boat_data = [
    #         {"boat_id": f"boat_{i + 1}", "location": generate_location()}
    #         for i in range(3)  # Only 3 boats
    #     ]
    # print(f"Sending location data: {boat_data}")
    # socketio.emit('boat_locations', boat_data)
    emit('server_response', {'message': 'Connection established!'})

# Handle frontend disconnection
@socketio.on('disconnect')
def handle_disconnect():
    print('Frontend disconnected')
    # thread1.join()

def broadcast_locations():
    while True:
        boat_data = [
            {"boat_id": f"boat_{i + 1}", "location": generate_location()}
            for i in range(3)  # Only 3 boats
        ]
        # print(f"Sending location data: {boat_data}")
        socketio.emit('boat_locations', boat_data)
        socketio.sleep(2)  # Non-blocking delay

# Handle optional frontend data input
@socketio.on('gui_data')
def handle_gui_data(data):
    print('Received data from frontend:', data)
    emit('server_response', {'message': 'Data received successfully!'})



# Start the Flask-SocketIO server and background task
if __name__ == '__main__':
    print("Starting backend...")
    # Start the broadcast task as a background thread
    socketio.run(app, host='0.0.0.0', port=3336, debug=True)
