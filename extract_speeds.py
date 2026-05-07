import pandas as pd
import numpy as np

# Load parquet file
df = pd.read_parquet("yellow_tripdata_2023-01.parquet")

# Keep required columns
df = df[[
    "trip_distance",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime"
]]

# Convert times
df["pickup"] = pd.to_datetime(df["tpep_pickup_datetime"])
df["dropoff"] = pd.to_datetime(df["tpep_dropoff_datetime"])

# Compute trip duration in hours
df["duration_hours"] = (
    (df["dropoff"] - df["pickup"]).dt.total_seconds() / 3600
)

# Remove invalid rows
df = df[
    (df["duration_hours"] > 0) &
    (df["trip_distance"] > 0)
]

# Compute speed
df["speed_mph"] = df["trip_distance"] / df["duration_hours"]

# Remove unrealistic speeds
df = df[
    (df["speed_mph"] >= 5) &
    (df["speed_mph"] <= 70)
]

# Save speeds
speeds = df["speed_mph"].tolist()

np.save("nyc_speeds.npy", np.array(speeds))

print(f"Saved {len(speeds)} speed samples.")