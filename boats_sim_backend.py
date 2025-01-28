import gevent.monkey
gevent.monkey.patch_all()
import gevent
import math
import random
import uuid
import time

from flask import Flask, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# -------------------------------
# SIMULATION PARAMETERS
# -------------------------------
BASE_LAT = 37.86706
BASE_LON = -122.36341
MAX_SPEED = 0.0005
NUM_BOATS = 10

# -------------------------------
# FLASK & SOCKET.IO SETUP
# -------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='gevent',
    ping_interval=60,
    ping_timeout=180
)

# -------------------------------
# BOAT CLASS FOR SIMULATION
# -------------------------------
class Boat:
    def __init__(self, boat_id):
        self.boat_id = boat_id
        self.lat = BASE_LAT + random.uniform(-0.005, 0.005)
        self.lng = BASE_LON + random.uniform(-0.005, 0.005)

        # Velocity dict simulates incremental movement
        self.velocity = {"lat": 0.0, "lng": 0.0}

        # Extra simulated data
        self.u_wind = random.uniform(-3, 3)
        self.v_wind = random.uniform(-3, 3)
        self.temperature = random.uniform(60, 80)  # Fahrenheit
        self.chaos = random.uniform(0, 2)
        self.status = "station-keeping"
        self.notification = None

        # Target coordinates (for auto mode)
        self.target_lat = None
        self.target_lng = None
        self.start_lat = self.lat
        self.start_lng = self.lng

    def update(self):
        # If we have a target set, move toward it
        if self.target_lat is not None and self.target_lng is not None:
            dir_lat = self.target_lat - self.lat
            dir_lng = self.target_lng - self.lng
            distance = math.hypot(dir_lat, dir_lng)

            if distance > 0:
                # Normalize direction
                dir_lat /= distance
                dir_lng /= distance

                # Decide movement (avoid overshooting)
                move_dist = min(distance, MAX_SPEED)
                self.velocity["lat"] = dir_lat * move_dist
                self.velocity["lng"] = dir_lng * move_dist

                # Update position
                self.lat += self.velocity["lat"]
                self.lng += self.velocity["lng"]

                # Progress percentage
                total_distance = math.hypot(
                    self.target_lat - self.start_lat, 
                    self.target_lng - self.start_lng
                )
                if total_distance == 0:
                    progress = 100
                else:
                    progress = 100 - (distance / total_distance * 100)
                progress = max(0, min(100, progress))  # clamp

                self.status = f"In Progress ({progress:.1f}%)"

                # Reached target?
                if distance <= MAX_SPEED:
                    self._reach_target()
            else:
                self._reach_target()
        else:
            # No target => station-keeping
            self.velocity["lat"] = 0
            self.velocity["lng"] = 0
            self.status = "station-keeping"

        # Randomly adjust wind
        self.u_wind += random.uniform(-0.1, 0.1)
        self.v_wind += random.uniform(-0.1, 0.1)

        # Chaos scales with speed
        speed = math.hypot(self.velocity["lat"], self.velocity["lng"])
        self.chaos = speed * 1e4

        # Random slight temperature changes
        self.temperature += random.uniform(-0.1, 0.1)

    def _reach_target(self):
        """Boat has reached its target."""
        self.lat = self.target_lat
        self.lng = self.target_lng
        self.target_lat = None
        self.target_lng = None
        self.velocity["lat"] = 0
        self.velocity["lng"] = 0
        self.status = "Reached Destination"
        self.notification = {
            "id": str(uuid.uuid4()),
            "type": "reached"
        }

    def get_state_dict(self):
        """
        Return the boat state in a dict. 
        We'll transform this slightly for the 'boat_list' format below.
        """
        return {
            "boat_id": self.boat_id,
            "latitude": round(self.lat, 6),
            "longitude": round(self.lng, 6),
            "wind_dir_u": round(self.u_wind, 2),
            "wind_dir_v": round(self.v_wind, 2),
            "chaos": round(self.chaos, 2),
            "temperature": round(self.temperature, 1),
            "velocity": {
                "lat": round(self.velocity["lat"], 6),
                "lng": round(self.velocity["lng"], 6),
            },
            "status": self.status,
        }

# -------------------------------
# CREATE SIMULATED BOATS
# -------------------------------
boats = [Boat(f"boat_{i+1}") for i in range(NUM_BOATS)]

# -------------------------------
# BACKGROUND TASK
# -------------------------------
def broadcast_locations():
    """
    Update boat states and emit 'boat_locations' data 
    at regular intervals (1 second).
    """
    while True:
        updated_list = []
        for b in boats:
            b.update()
            updated_list.append(_to_frontend_format(b))
        # print("updated_list", updated_list)
        socketio.emit('boat_locations', updated_list)
        socketio.sleep(1)

def _to_frontend_format(boat_obj):
    """
    Convert a Boat's state into the structure 
    you typically send to the frontend:

    [
      {
        "boat_id": "boat_1",
        "latitude": 37....,
        "longitude": -122....,
        "wind_dir_u": ...,
        "wind_dir_v": ...,
        ...
      },
      ...
    ]
    """
    state = boat_obj.get_state_dict()
    return state


# -------------------------------
# SOCKET.IO HANDLERS
# -------------------------------
@socketio.on('connect')
def handle_connect():
    print("Frontend connected:", request.sid)
    emit('server_response', {'message': 'Simulation connection established!'})
    # Start broadcasting in a background task
    socketio.start_background_task(broadcast_locations)

@socketio.on('disconnect')
def handle_disconnect():
    print("Frontend disconnected:", request.sid)

@socketio.on('request_boat_list')
def handle_request_boat_list():
    """
    Mimics the event in your original code to send the list of boats 
    in the same structure:
      [{'boat_id': boat_id, 'data': {...}}, ... ]
    """
    try:
        boat_list = []
        for b in boats:
            boat_list.append(_to_frontend_format(b))

        emit('boat_locations', boat_list)
        print("Sent boat list to frontend.")
        print(f"boats connected: {len(boat_list)}")
    except Exception as e:
        print(f"Error in handle_request_boat_list: {e}")

@socketio.on('gui_data')
def handle_gui_data(data):
    """
    This imitates your XBee code structure:
    data = {
      "id": "<boat_id>",
      "md": "auto" or "mnl",
      "tlat": <target_lat>,
      "tlng": <target_lng>,
      ...
    }
    """
    try:
        boat_id = data.get('id')
        mode = data.get('md')  # "auto" or "mnl"

        if not boat_id:
            print("No boat_id provided in gui_data")
            return

        # Find the boat
        target_boat = next((b for b in boats if b.boat_id == boat_id), None)
        if not target_boat:
            print(f"Boat {boat_id} not found in simulation.")
            return

        if mode == 'auto':
            # Use target lat/lng
            tlat = data.get('tlat')
            tlng = data.get('tlng')
            if tlat is not None and tlng is not None:
                target_boat.target_lat = float(tlat)
                target_boat.target_lng = float(tlng)
                target_boat.start_lat = target_boat.lat
                target_boat.start_lng = target_boat.lng
                target_boat.status = "In Progress (0%)"
                print(f"Set AUTO mode for {boat_id} => Target: ({tlat}, {tlng})")

        elif mode == 'mnl':
            # Example: manual inputs (rudder, sail, heading)
            rudder = data.get('r', 0)
            sail = data.get('s', 0)
            heading = data.get('th', 0)
            print(f"{boat_id} in MNL mode => rudder={rudder}, sail={sail}, heading={heading}")
            # In simulation, you could do something with these values if you wish.

        else:
            print(f"Invalid mode '{mode}' for boat {boat_id}")

        # Send a confirmation to the frontend
        emit('server_response', {'message': f"Data received for {boat_id} (mode={mode})"})

    except Exception as e:
        print(f"Error in handle_gui_data: {e}")

# -------------------------------
# RUN THE SERVER
# -------------------------------
if __name__ == '__main__':
    print("Starting simulation backend...")
    socketio.run(app, host='0.0.0.0', port=3336, debug=True)
