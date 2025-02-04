#!/usr/bin/env python3
import csv
import random
from datetime import datetime, timedelta

# Configuration
NUM_BOATS = 50           # Generate boats B1 to B50
NUM_DATA_POINTS = 100    # N sets of data points per boat (adjust as needed)

# Center coordinate around which to generate latitude and longitude
CENTER_LAT = 37.868404
CENTER_LON = -122.371044

# Define random ranges for the simulation values
LAT_RANGE = 0.01         # ±0.01 degrees from CENTER_LAT
LON_RANGE = 0.01         # ±0.01 degrees from CENTER_LON
WIND_VELOCITY_RANGE = (0, 150)  # e.g., 0 to 150 (units can be mph, km/h, etc.)
TEMPERATURE_RANGE = (-10, 40)   # Celsius values
HEADING_RANGE = (0, 360)        # Degrees from 0 to 360
ACCELERATION_RANGE = (-2, 2)    # Acceleration components range

# Starting time for simulation data
start_time = datetime.now()

# CSV file header
header = [
    "boat_id",
    "time_now",
    "latitude",
    "longitude",
    "wind_velocity",
    "temperature",
    "heading",
    "acceleration_x",
    "acceleration_y",
    "acceleration_z"
]

output_filename = "simulation_data.csv"

with open(output_filename, mode="w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(header)

    for boat in range(1, NUM_BOATS + 1):
        boat_id = f"B{boat}"
        for i in range(NUM_DATA_POINTS):
            # Randomize latitude and longitude near the center coordinate
            latitude = CENTER_LAT + random.uniform(-LAT_RANGE, LAT_RANGE)
            longitude = CENTER_LON + random.uniform(-LON_RANGE, LON_RANGE)

            # Randomize other measurements
            wind_velocity = round(random.uniform(*WIND_VELOCITY_RANGE), 2)
            temperature = round(random.uniform(*TEMPERATURE_RANGE), 2)
            heading = round(random.uniform(*HEADING_RANGE), 2)
            acceleration_x = round(random.uniform(*ACCELERATION_RANGE), 3)
            acceleration_y = round(random.uniform(*ACCELERATION_RANGE), 3)
            acceleration_z = round(random.uniform(*ACCELERATION_RANGE), 3)

            # Create a timestamp for the data point (increment 1 second per point)
            time_now = (start_time + timedelta(seconds=i)).isoformat() + "Z"

            # Write the row to CSV
            row = [
                boat_id,
                time_now,
                latitude,
                longitude,
                wind_velocity,
                temperature,
                heading,
                acceleration_x,
                acceleration_y,
                acceleration_z,
            ]
            writer.writerow(row)

print(f"Simulation data generated for {NUM_BOATS} boats with {NUM_DATA_POINTS} data points each.")
print(f"Data written to '{output_filename}'.")
