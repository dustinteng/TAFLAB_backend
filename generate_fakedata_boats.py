# generate_boats.py

import json
import random

def generate_boat_data(num_boats, center_lat, center_lng, lat_range, lng_range):
    boats = []
    for i in range(1, num_boats + 1):
        # Generate random latitude and longitude around the center point
        lat = center_lat + random.uniform(-lat_range, lat_range)
        lng = center_lng + random.uniform(-lng_range, lng_range)
        
        # Generate random wind vector components (u and v)
        u = random.uniform(-5, 5)  # East-West component
        v = random.uniform(-5, 5)  # North-South component
        
        # Generate random chaos value
        chaos = random.uniform(0.5, 1.5)  # Chaos could represent wave height variability

        boat = {
            "boat_number": i,
            "lat": lat,
            "lng": lng,
            "u": u,
            "v": v,
            "chaos": chaos  # Add chaos property to each boat
        }
        boats.append(boat)
    return boats

def main():
    num_boats = 1000
    center_lat = 37.86374  # Center around Berkeley, CA
    center_lng = -122.35495
    lat_range = 0.1 # Range for latitude variation (~1 km)
    lng_range = 0.1  # Range for longitude variation (~1 km)

    boats = generate_boat_data(num_boats, center_lat, center_lng, lat_range, lng_range)
    
    # Save to boats.json
    with open('boats.json', 'w') as f:
        json.dump(boats, f, indent=2)

if __name__ == "__main__":
    main()
