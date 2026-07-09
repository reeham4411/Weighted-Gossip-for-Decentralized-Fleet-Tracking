"""
Extract real-world vehicle speeds from NYC TLC Yellow Taxi trip data.

Supports ONE file (original behavior) or MANY files (extend the dataset
across multiple months) by matching a glob pattern.

USAGE (from repo root):
    # drop downloaded parquet files into data/raw/, named like
    # yellow_tripdata_2026-01.parquet, yellow_tripdata_2026-02.parquet, ...
    python3 src/extract_speeds.py
    # auto-detects every matching file in data/raw/ and combines them —
    # no code changes needed to add more months.
"""

import glob
import os
import pandas as pd
import numpy as np

# Matches yellow_tripdata_2023-01.parquet, yellow_tripdata_2026-04.parquet, etc.
# Add more files to data/raw/ and they'll be picked up automatically — no
# code changes needed to extend the dataset to more months.
FILE_PATTERN = "data/raw/yellow_tripdata_*.parquet"
OUTPUT_PATH  = "data/processed/nyc_speeds.npy"

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
            f"No files matching '{FILE_PATTERN}'. Download at least one NYC "
            f"TLC yellow taxi parquet file into data/raw/ (see "
            f"docs/EXPERIMENT_README.md for the download link)."
        )

    print(f"Found {len(files)} file(s) matching '{FILE_PATTERN}':")

    all_speeds = []

    for path in files:
        speeds = extract_speeds_from_file(path)
        all_speeds.append(speeds)
        print(f"  {path}: {len(speeds)} valid speed samples")

    combined = pd.concat(all_speeds, ignore_index=True)
    # float32 is plenty of precision for a 5-70mph range and roughly halves
    # the file size vs. pandas' default float64 — matters once you're
    # combining several months' worth of samples.
    speeds_array = combined.to_numpy().astype(np.float32)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    np.save(OUTPUT_PATH, speeds_array)

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\nSaved {len(speeds_array)} total speed samples from {len(files)} file(s) "
          f"to {OUTPUT_PATH} ({size_mb:.1f} MB)")
    print(f"Speed range: {speeds_array.min():.1f}-{speeds_array.max():.1f} mph, "
          f"mean {speeds_array.mean():.1f} mph, std {speeds_array.std():.1f} mph")


if __name__ == "__main__":
    main()