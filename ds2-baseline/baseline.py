import sys
from pathlib import Path

import pandas as pd


# Add project root so this script can import the shared db.py.
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import db


SELECTED_RELATIVE_THRESHOLD = 1.50
SELECTED_ABSOLUTE_THRESHOLD = 500
SELECTED_MIN_OBSERVATIONS = 10


def load_hourly_data(conn):
    """Load historical hourly pedestrian counts."""

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

    numeric_columns = [
        "location_id",
        "day_of_week",
        "hourday",
        "pedestrian_count",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column])

    return df


def calculate_baseline(df):
    """
    Calculate the historical baseline for each:

        sensor x weekday x hour

    Median is used by DS3 for sensory scoring.
    Mean is also stored because the database schema requires it.
    """

    return (
        df.groupby(
            [
                "location_id",
                "day_of_week",
                "hourday",
            ]
        )
        .agg(
            average_count=(
                "pedestrian_count",
                "mean",
            ),
            median_count=(
                "pedestrian_count",
                "median",
            ),
            observation_count=(
                "pedestrian_count",
                "size",
            ),
        )
        .reset_index()
    )


def check_baseline(baseline):
    """Print a short validation summary before writing to MySQL."""

    print("\nBaseline summary:")
    print(f"Baseline slots: {len(baseline):,}")
    print(
        f"Sensors represented: "
        f"{baseline['location_id'].nunique()}"
    )

    print("\nObservation-count distribution:")
    print(
        baseline["observation_count"].describe()
    )

    weak = baseline[
        baseline["observation_count"]
        < SELECTED_MIN_OBSERVATIONS
    ]

    print(
        f"\nSlots below minimum observation requirement "
        f"({SELECTED_MIN_OBSERVATIONS}): "
        f"{len(weak):,}"
    )


def save_baseline(conn, baseline):
    """
    Insert or update baseline rows.

    The primary key is:
        location_id + day_of_week + hourday

    ON DUPLICATE KEY UPDATE allows this script to be rerun safely.
    """

    sql = """
        INSERT INTO baseline (
            location_id,
            day_of_week,
            hourday,
            average_count,
            median_count,
            observation_count,
            recomputed_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            NOW()
        )
        ON DUPLICATE KEY UPDATE
            average_count = VALUES(average_count),
            median_count = VALUES(median_count),
            observation_count = VALUES(observation_count),
            recomputed_at = NOW()
    """

    rows = [
        (
            int(row.location_id),
            int(row.day_of_week),
            int(row.hourday),
            float(row.average_count),
            float(row.median_count),
            int(row.observation_count),
        )
        for row in baseline.itertuples(index=False)
    ]

    with conn.cursor() as cur:
        cur.executemany(
            sql,
            rows,
        )

    conn.commit()

    print(
        f"\nBaseline rows written: "
        f"{len(rows):,}"
    )


def save_config(conn):
    """
    Store the selected DS2 defaults in the config table.

    These values can later be read by DS3 rather than hardcoded
    into sensory-scoring logic.
    """

    configs = [
        (
            "relative_threshold",
            str(SELECTED_RELATIVE_THRESHOLD),
            "HIGH requires current count to be at least 1.5 times the historical median.",
        ),
        (
            "absolute_threshold",
            str(SELECTED_ABSOLUTE_THRESHOLD),
            "Default minimum pedestrian count required before a reading can be considered HIGH.",
        ),
        (
            "minimum_observations",
            str(SELECTED_MIN_OBSERVATIONS),
            "Minimum historical observations required for a reliable baseline.",
        ),
    ]

    sql = """
        INSERT INTO config (
            config_key,
            value,
            updated_at,
            note
        )
        VALUES (
            %s,
            %s,
            NOW(),
            %s
        )
        ON DUPLICATE KEY UPDATE
            value = VALUES(value),
            updated_at = NOW(),
            note = VALUES(note)
    """

    with conn.cursor() as cur:
        cur.executemany(
            sql,
            configs,
        )

    conn.commit()

    print("\nConfig values written:")
    for key, value, _ in configs:
        print(
            f"  {key} = {value}"
        )


def verify_saved_data(conn):
    """Check that baseline and config values were saved successfully."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM baseline
            """
        )

        baseline_count = cur.fetchone()["n"]

        cur.execute(
            """
            SELECT
                config_key,
                value,
                updated_at
            FROM config
            ORDER BY config_key
            """
        )

        configs = cur.fetchall()

    print(
        f"\nBaseline rows currently in database: "
        f"{baseline_count:,}"
    )

    print("\nCurrent config:")

    for row in configs:
        print(
            f"  {row['config_key']} = "
            f"{row['value']}"
        )


def main():
    """Calculate and store the DS2 historical baseline."""

    conn = db.connect()

    try:
        print(
            "Loading historical pedestrian data..."
        )

        df = load_hourly_data(conn)

        print(
            f"Historical records loaded: "
            f"{len(df):,}"
        )

        baseline = calculate_baseline(df)

        check_baseline(
            baseline
        )

        save_baseline(
            conn,
            baseline,
        )

        save_config(
            conn
        )

        verify_saved_data(
            conn
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()