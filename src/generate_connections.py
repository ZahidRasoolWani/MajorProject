import pandas as pd
import sqlite3
from math import radians, sin, cos, sqrt, atan2

# Load GTFS CSV files
stop_times = pd.read_csv("stop_times.csv", dtype={"stop_id": str, "trip_id": str})
stops = pd.read_csv("stops.csv", dtype={"stop_id": str})

# Merge stop lat/lon for distance calculation
stops_geo = stops[['stop_id', 'stop_lat', 'stop_lon']].drop_duplicates()
stop_times = stop_times.merge(stops_geo, on="stop_id", how="left")

# Sort by trip_id and stop_sequence
stop_times.sort_values(by=["trip_id", "stop_sequence"], inplace=True)

# Haversine function
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# Generate connections
connections = []
for trip_id, group in stop_times.groupby("trip_id"):
    group = group.reset_index(drop=True)
    for i in range(len(group) - 1):
        from_row = group.iloc[i]
        to_row = group.iloc[i + 1]

        if pd.isna(from_row.stop_lat) or pd.isna(to_row.stop_lat):
            continue

        distance = haversine(from_row.stop_lat, from_row.stop_lon, to_row.stop_lat, to_row.stop_lon)
        connections.append((
            from_row.stop_id,
            to_row.stop_id,
            trip_id,
            from_row.departure_time,
            to_row.arrival_time,
            distance
        ))

# Connect to DB
conn = sqlite3.connect("bmtc_routes.db")
cur = conn.cursor()

# Create table
cur.execute("DROP TABLE IF EXISTS connections")
cur.execute("""
CREATE TABLE connections (
  from_stop_id TEXT,
  to_stop_id TEXT,
  trip_id TEXT,
  departure_time TEXT,
  arrival_time TEXT,
  distance REAL
)
""")

# Insert connections
cur.executemany("""
INSERT INTO connections (from_stop_id, to_stop_id, trip_id, departure_time, arrival_time, distance)
VALUES (?, ?, ?, ?, ?, ?)
""", connections)

conn.commit()
conn.close()

print(f"✅ Done! Inserted {len(connections):,} connections into 'connections' table.")
