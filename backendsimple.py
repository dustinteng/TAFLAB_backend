import gevent.monkey
gevent.monkey.patch_all()
import gevent

from flask import Flask
from flask_socketio import SocketIO, emit
import random
import time
import threading

# Create a Flask application
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Base coordinates near the target location
BASE_LAT = 37.866942
BASE_LON = -122.315452

# Generate a slightly random position around the base coordinates
def generate_location():
    return {
        "latitude": BASE_LAT + random.uniform(-0.01, 0.01),
        "longitude": BASE_LON + random.uniform(-0.01, 0.01)
    }

# Emit location updates for 5 boats every 2 seconds
def broadcast_locations():
    while True:
        boat_data = [
            {"boat_id": f"boat_{i + 1}", "location": generate_location()}
            for i in range(5)
        ]
        print(f"Sending location data: {boat_data}")
        socketio.emit('boat_locations', boat_data, to='/')
        gevent.sleep(2)  # Use gevent sleep for non-blocking delay


# Start the location broadcasting in a separate thread
@socketio.on('connect')
def handle_connect():
    print('Frontend connected')
    emit('server_response', {'message': 'Connection established!'}, broadcast=True)

    # Start broadcasting locations in a background thread if not already started
    threading.Thread(target=broadcast_locations, daemon=True).start()

@socketio.on('gui_data')
def handle_gui_data(data):
    print('Received data from frontend:', data)
    emit('server_response', {'message': 'Data received successfully!'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Frontend disconnected')
    emit('server_response', {'message': 'A client has disconnected!'}, broadcast=True)

# Start the server
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=3336, debug=True)
