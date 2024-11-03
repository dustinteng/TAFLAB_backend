import gevent.monkey
gevent.monkey.patch_all()
import gevent

from flask import Flask
from flask_socketio import SocketIO, emit
import random
import uuid
import math

# Create a Flask application
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Base coordinates near the target location
BASE_LAT = 37.86706
BASE_LON = -122.36341

# Maximum speed (adjust as needed)
MAX_SPEED = 0.0005  # This represents the maximum distance the boat can move per update

# Define a Boat class to store state
class Boat:
    def __init__(self, boat_id):
        self.boat_id = boat_id
        self.boat_number = int(boat_id.split('_')[1])  # Assuming boat_id is 'boat_N'
        self.lat = BASE_LAT + random.uniform(-0.005, 0.005)
        self.lng = BASE_LON + random.uniform(-0.005, 0.005)
        self.velocity = {
            "lat": 0.0,
            "lng": 0.0
        }
        # Initialize u-wind and v-wind, chaos, temperature
        self.u_wind = random.uniform(-3, 3)  # Wind component in u-direction
        self.v_wind = random.uniform(-3, 3)  # Wind component in v-direction
        self.temperature = random.uniform(60, 80)  # Temperature in Fahrenheit
        self.chaos = random.uniform(0, 2)  # Initial chaos value

        # Add target latitude and longitude
        self.target_lat = None
        self.target_lng = None
        self.status = "Idle"
        self.notification = None

    def update(self):
        if self.target_lat is not None and self.target_lng is not None:
            # Compute direction towards the target
            dir_lat = self.target_lat - self.lat
            dir_lng = self.target_lng - self.lng

            # Compute distance to the target
            distance = math.hypot(dir_lat, dir_lng)

            if distance > 0:
                # Normalize the direction vector
                dir_lat /= distance
                dir_lng /= distance

                # Determine movement distance (don't overshoot the target)
                move_dist = min(distance, MAX_SPEED)

                # Set velocity towards the target
                self.velocity["lat"] = dir_lat * move_dist
                self.velocity["lng"] = dir_lng * move_dist

                # Update position based on velocity
                self.lat += self.velocity["lat"]
                self.lng += self.velocity["lng"]

                # Update status with progress percentage
                total_distance = math.hypot(self.target_lat - self.start_lat, self.target_lng - self.start_lng)
                progress = 100 - (distance / total_distance * 100)
                progress = max(0, min(100, progress))  # Clamp progress between 0 and 100
                self.status = f"In Progress ({progress:.1f}%)"

                # Check if the boat has reached the target
                if distance <= MAX_SPEED:
                    # Target reached
                    print(f"{self.boat_id} has reached the target.")
                    self.lat = self.target_lat
                    self.lng = self.target_lng
                    self.target_lat = None
                    self.target_lng = None
                    # Stop the boat
                    self.velocity["lat"] = 0
                    self.velocity["lng"] = 0
                    self.status = "Reached Destination"
                    # Set notification
                    self.notification = {
                        "id": str(uuid.uuid4()),
                        "type": "reached"
                    }
            else:
                # Target reached (distance is zero)
                self.lat = self.target_lat
                self.lng = self.target_lng
                self.target_lat = None
                self.target_lng = None
                self.velocity["lat"] = 0
                self.velocity["lng"] = 0
                self.status = "Reached Destination"
                # Set notification
                self.notification = {
                    "id": str(uuid.uuid4()),
                    "type": "reached"
                }
        else:
            # No target set; boat remains idle
            self.velocity["lat"] = 0
            self.velocity["lng"] = 0
            self.status = "Idle"

        # Keep boats within certain bounds (optional)
        # lat_range = (BASE_LAT - 0.01, BASE_LAT + 0.01)
        # lng_range = (BASE_LON - 0.01, BASE_LON + 0.01)
        # self.lat = max(min(self.lat, lat_range[1]), lat_range[0])
        # self.lng = max(min(self.lng, lng_range[1]), lng_range[0])

        # Simulate u-wind and v-wind (could be based on velocity or random)
        self.u_wind += random.uniform(-0.1, 0.1)
        self.v_wind += random.uniform(-0.1, 0.1)

        # Update chaos (could be based on speed)
        speed = math.hypot(self.velocity["lat"], self.velocity["lng"])
        self.chaos = speed * 1e4  # Scale appropriately

        # Update temperature (could be random fluctuations)
        self.temperature += random.uniform(-0.1, 0.1)

    def get_state(self):
        state = {
            "boat_id": self.boat_id,
            "boat_number": self.boat_number,
            "lat": round(self.lat, 6),  # Latitude rounded to 6 decimal places
            "lng": round(self.lng, 6),  # Longitude rounded to 6 decimal places
            "u-wind": float(self.u_wind),
            "v-wind": float(self.v_wind),
            "chaos": float(self.chaos),
            "temperature": round(float(self.temperature), 1),  # Temperature rounded to 1 decimal place
            "velocity": {
                "lat": float(self.velocity["lat"]),
                "lng": float(self.velocity["lng"]),
            },
            "status": self.status,
        }
        if self.notification:
            state["notification"] = self.notification
            self.notification = None  # Reset notification after sending
        return state

# Initialize boats
boats = [Boat(f"boat_{i+1}") for i in range(10)]

# Emit location updates for boats every 1 second
def broadcast_locations():
    while True:
        boat_data = []
        for boat in boats:
            boat.update()
            boat_data.append(boat.get_state())

        socketio.emit('boat_locations', boat_data)
        socketio.sleep(1)

# Start the location broadcasting in a background task
@socketio.on('connect')
def handle_connect():
    print('Frontend connected')
    emit('server_response', {'message': 'Connection established!'})

    # Start broadcasting locations in a background task
    socketio.start_background_task(broadcast_locations)

@socketio.on('gui_data')
def handle_gui_data(data):
    print('Received data from frontend:', data)
    boat_name = data.get('boat_name')
    command_mode = data.get('command_mode')

    if command_mode == 'autonomous' and boat_name:
        target_lat = data.get('target_gps_latitude')
        target_lng = data.get('target_gps_longitude')

        # Find the boat with the specified name
        for boat in boats:
            if boat.boat_id == boat_name:
                boat.target_lat = target_lat
                boat.target_lng = target_lng
                boat.start_lat = boat.lat  # Record starting position
                boat.start_lng = boat.lng
                boat.status = "In Progress (0%)"
                print(f'Set target for {boat_name} to ({target_lat}, {target_lng})')
                break

    emit('server_response', {'message': 'Data received successfully!'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Frontend disconnected')

# Start the server
if __name__ == '__main__':
    print("Starting backend...")
    socketio.run(app, host='0.0.0.0', port=3336, debug=True)
