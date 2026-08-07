import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import db


def test_connection(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM pedestrian_count_hour")
        result = cur.fetchone()

    print(f"Historical rows: {result['n']:,}")


def load_hourly_data(conn):
    query = """
        SELECT
            location_id,
            day_of_week,
            hourday,
            pedestrian_count
        FROM pedestrian_count_hour
    """

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    df = pd.DataFrame(rows)

    # Ensure numeric types
    df["location_id"] = pd.to_numeric(df["location_id"])
    df["day_of_week"] = pd.to_numeric(df["day_of_week"])
    df["hourday"] = pd.to_numeric(df["hourday"])
    df["pedestrian_count"] = pd.to_numeric(df["pedestrian_count"])

    return df


def check_data(df):
    print("\nMissing values:")
    print(df.isnull().sum())

    print("\nPedestrian count summary:")
    print(df["pedestrian_count"].describe())

    print("\nDay of week:")
    print(sorted(df["day_of_week"].unique()))

    print("\nHours:")
    print(sorted(df["hourday"].unique()))

    print("\nNumber of sensors:")
    print(df["location_id"].nunique())


def calculate_baseline(df):
    baseline = (
        df.groupby(
            ["location_id", "day_of_week", "hourday"]
        )
        .agg(
            median_count=("pedestrian_count", "median"),
            observation_count=("pedestrian_count", "size")
        )
        .reset_index()
    )

    return baseline


def check_baseline(baseline):
    print("\nObservation count summary:")
    print(baseline["observation_count"].describe())

    weak = baseline[
        baseline["observation_count"] < 10
    ]

    print("\nBaseline slots with fewer than 10 observations:")
    print(weak.head(20))

    print(f"\nTotal weak baseline slots: {len(weak)}")


def check_sensor_coverage(conn, baseline):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT location_id
            FROM location
            WHERE location_type = 'sensor'
        """)

        all_sensors = {
            row["location_id"]
            for row in cur.fetchall()
        }

    baseline_sensors = set(
        baseline["location_id"].unique()
    )

    missing = all_sensors - baseline_sensors

    print("\nSensor coverage:")
    print(f"Total registered sensors: {len(all_sensors)}")
    print(f"Sensors with historical baseline: {len(baseline_sensors)}")
    print(f"Sensors without historical baseline: {len(missing)}")
    print(f"Missing sensor IDs: {sorted(missing)}")

if __name__ == "__main__":
    conn = db.connect()

    # 1. Test database
    test_connection(conn)

    # 2. Load historical pedestrian data
    df = load_hourly_data(conn)

    print("\nFirst five historical records:")
    print(df.head())

    print(f"\nDataset shape: {df.shape}")

    # 3. Check historical data
    check_data(df)

    # 4. Calculate baseline
    baseline = calculate_baseline(df)

    print("\nFirst 20 baseline records:")
    print(baseline.head(20))

    print(f"\nTotal baseline slots: {len(baseline)}")

    # 5. Check baseline quality
    check_baseline(baseline)

    check_sensor_coverage(conn, baseline)
    
    conn.close()