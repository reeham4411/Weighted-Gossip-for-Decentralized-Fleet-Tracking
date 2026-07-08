"""
Extract real-world vehicle speeds from NYC TLC Yellow Taxi trip data.

Supports ONE file (original behavior) or MANY files (extend the dataset
across multiple months) by matching a glob pattern.

USAGE:
    # single month (original behavior, still works exactly the same)
    python3 extract_speeds.py

    # multiple months — put all downloaded parquet files in this folder
    # named like yellow_tripdata_2023-01.parquet, yellow_tripdata_2023-02.parquet, ...
    # then just run the same command — it auto-detects all matching files
    python3 extract_speeds.py
"""

import glob
import pandas as pd
import numpy as np

# Matches yellow_tripdata_2023-01.parquet, yellow_tripdata_2023-02.parquet, etc.
# Add more files to the folder and they'll be picked up automatically —
# no code changes needed to extend the dataset to more months.
FILE_PATTERN = "yellow_tripdata_*.parquet"

REQUIRED_COLUMNS = [
    "trip_distance",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
]


def extract_speeds_from_file(path):
    """Load one parquet file and return a cleaned speed_mph Series."""
    df = pd.read_parquet(path)
    df = df[REQUIRED_COLUMNS]

    df["pickup"] = pd.to_datetime(df["tpep_pickup_datetime"])
    df["dropoff"] = pd.to_datetime(df["tpep_dropoff_datetime"])

    df["duration_hours"] = (
        (df["dropoff"] - df["pickup"]).dt.total_seconds() / 3600
    )

    df = df[
        (df["duration_hours"] > 0) &
        (df["trip_distance"] > 0)
    ]

    df["speed_mph"] = df["trip_distance"] / df["duration_hours"]

    df = df[
        (df["speed_mph"] >= 5) &
        (df["speed_mph"] <= 70)
    ]

    return df["speed_mph"]


def main():
    files = sorted(glob.glob(FILE_PATTERN))

    if not files:
        raise FileNotFoundError(
            f"No files matching '{FILE_PATTERN}' found in the current folder. "
            f"Download at least one NYC TLC yellow taxi parquet file and place "
            f"it here (see EXPERIMENT_README.md for the download link)."
        )

    print(f"Found {len(files)} file(s) matching '{FILE_PATTERN}':")

    all_speeds = []

    for path in files:
        speeds = extract_speeds_from_file(path)
        all_speeds.append(speeds)
        print(f"  {path}: {len(speeds)} valid speed samples")

    combined = pd.concat(all_speeds, ignore_index=True)
    speeds_array = combined.to_numpy()

    np.save("nyc_speeds.npy", speeds_array)

    print(f"\nSaved {len(speeds_array)} total speed samples from {len(files)} file(s) "
          f"to nyc_speeds.npy")
    print(f"Speed range: {speeds_array.min():.1f}-{speeds_array.max():.1f} mph, "
          f"mean {speeds_array.mean():.1f} mph, std {speeds_array.std():.1f} mph")


if __name__ == "__main__":
    main()
