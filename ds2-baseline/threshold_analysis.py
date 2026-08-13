import sys
from pathlib import Path

import pandas as pd


# ==========================================================
# PROJECT SETUP
# ==========================================================

# Add project root so this script can import shared db.py.
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import db


# ==========================================================
# THRESHOLD SETTINGS
# ==========================================================

# Relative thresholds tested for both hourly and minute data.
RELATIVE_THRESHOLDS = [1.25, 1.50, 1.75, 2.00]

# Absolute thresholds tested for HOURLY data only.
ABSOLUTE_THRESHOLDS = [250, 500, 750, 1000]

# Selected hourly defaults from historical analysis.
SELECTED_RELATIVE_THRESHOLD = 1.50
SELECTED_ABSOLUTE_THRESHOLD = 500
SELECTED_MIN_OBSERVATIONS = 10

# Peak commuter periods.
PEAK_HOURS = [7, 8, 9, 16, 17, 18]


# ==========================================================
# LOAD HOURLY DATA
# ==========================================================

def load_hourly_data(conn):
    """Load historical hourly pedestrian counts from MySQL."""

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
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=numeric_columns
    )

    return df


# ==========================================================
# LOAD PER-MINUTE DATA
# ==========================================================

def load_minute_data(conn):
    """Load per-minute pedestrian counts from MySQL."""

    query = """
        SELECT
            location_id,
            sensing_datetime,
            sensing_date,
            sensing_time,
            total_of_directions
        FROM pedestrian_count_minute
        WHERE total_of_directions IS NOT NULL
    """

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["location_id"] = pd.to_numeric(
        df["location_id"],
        errors="coerce",
    )

    df["pedestrian_count"] = pd.to_numeric(
        df["total_of_directions"],
        errors="coerce",
    )

    df["sensing_datetime"] = pd.to_datetime(
        df["sensing_datetime"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "location_id",
            "pedestrian_count",
            "sensing_datetime",
        ]
    )

    # Monday = 0, Sunday = 6.
    df["day_of_week"] = (
        df["sensing_datetime"].dt.dayofweek
    )

    df["hourday"] = (
        df["sensing_datetime"].dt.hour
    )

    df["minute"] = (
        df["sensing_datetime"].dt.minute
    )

    return df


# ==========================================================
# HOURLY BASELINE
# ==========================================================

def calculate_hourly_baseline(df):
    """
    Calculate historical hourly baseline for:

        sensor x weekday x hour
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


# ==========================================================
# MINUTE BASELINE
# ==========================================================

def calculate_minute_baseline(df):
    """
    Calculate per-minute baseline for:

        sensor x weekday x hour x minute

    Example:
        Sensor 1, Monday, 08:15
    """

    return (
        df.groupby(
            [
                "location_id",
                "day_of_week",
                "hourday",
                "minute",
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


# ==========================================================
# PREPARE ANALYSIS
# ==========================================================

def prepare_analysis(df, baseline, group_columns):
    """
    Join observations with their corresponding baseline.

    baseline_ratio =
        pedestrian_count / historical median
    """

    data = df.merge(
        baseline,
        on=group_columns,
        how="left",
    )

    # Ratios cannot be calculated against zero.
    data = data[
        data["median_count"] > 0
    ].copy()

    data["baseline_ratio"] = (
        data["pedestrian_count"]
        / data["median_count"]
    )

    return data


# ==========================================================
# RELATIVE THRESHOLD ANALYSIS
# ==========================================================

def analyse_relative_thresholds(
    data,
    name,
    thresholds=RELATIVE_THRESHOLDS,
):
    """Compare candidate relative thresholds."""

    results = []

    for threshold in thresholds:

        high = (
            data["baseline_ratio"]
            >= threshold
        )

        results.append(
            {
                "threshold": threshold,
                "high_records": int(
                    high.sum()
                ),
                "total_records": len(data),
                "high_percent": round(
                    high.mean() * 100,
                    2,
                ),
            }
        )

    results_df = pd.DataFrame(results)

    print(
        f"\n{name} relative threshold analysis:"
    )

    print(
        results_df.to_string(
            index=False
        )
    )

    return results_df


# ==========================================================
# BASELINE RATIO DISTRIBUTION
# ==========================================================

def analyse_ratio_distribution(data, name):
    """Display baseline-ratio distribution."""

    print(
        f"\n{name} baseline ratio distribution:"
    )

    print(
        data["baseline_ratio"].describe(
            percentiles=[
                0.50,
                0.75,
                0.90,
                0.95,
                0.99,
            ]
        )
    )


# ==========================================================
# OBSERVATION REQUIREMENTS
# ==========================================================

def analyse_observation_requirements(
    baseline,
    name,
):
    """Analyse baseline historical coverage."""

    print(
        f"\n{name} minimum observation analysis:"
    )

    for minimum in [
        5,
        10,
        20,
        30,
    ]:

        valid = (
            baseline["observation_count"]
            >= minimum
        )

        print(
            f"Minimum {minimum:2d}: "
            f"{valid.sum():,} / "
            f"{len(baseline):,} "
            f"({valid.mean() * 100:.2f}%) retained"
        )


# ==========================================================
# PEDESTRIAN COUNT DISTRIBUTION
# ==========================================================

def analyse_absolute_counts(
    data,
    name,
):
    """Analyse actual pedestrian counts."""

    print(
        f"\n{name} pedestrian count distribution:"
    )

    print(
        data["pedestrian_count"].describe(
            percentiles=[
                0.50,
                0.75,
                0.90,
                0.95,
                0.99,
            ]
        )
    )

    relative_high = data[
        data["baseline_ratio"]
        >= SELECTED_RELATIVE_THRESHOLD
    ]

    print(
        f"\n{name} pedestrian counts where "
        f"baseline ratio >= "
        f"{SELECTED_RELATIVE_THRESHOLD}:"
    )

    if relative_high.empty:
        print("No matching records.")

        return

    print(
        relative_high[
            "pedestrian_count"
        ].describe(
            percentiles=[
                0.10,
                0.25,
                0.50,
                0.75,
                0.90,
                0.95,
                0.99,
            ]
        )
    )


# ==========================================================
# EXTREME RATIOS
# ==========================================================

def inspect_extreme_ratios(
    data,
    name,
    limit=20,
):
    """Display observations with the largest baseline ratios."""

    columns = [
        "location_id",
        "day_of_week",
        "hourday",
    ]

    # Minute exists only for per-minute data.
    if "minute" in data.columns:
        columns.append(
            "minute"
        )

    columns += [
        "pedestrian_count",
        "median_count",
        "observation_count",
        "baseline_ratio",
    ]

    extreme = (
        data[columns]
        .sort_values(
            "baseline_ratio",
            ascending=False,
        )
        .head(limit)
    )

    print(
        f"\n{name} top {limit} baseline ratios:"
    )

    print(
        extreme.to_string(
            index=False
        )
    )


# ==========================================================
# HOURLY COMBINED THRESHOLD ANALYSIS
# ==========================================================

def analyse_hourly_combined_thresholds(
    data,
    name,
):
    """
    Test hourly relative + absolute thresholds.

    HIGH candidate:

        ratio >= 1.5
        AND
        hourly pedestrian count >= absolute threshold
    """

    results = []

    for absolute_threshold in ABSOLUTE_THRESHOLDS:

        high = (
            data["baseline_ratio"]
            >= SELECTED_RELATIVE_THRESHOLD
        ) & (
            data["pedestrian_count"]
            >= absolute_threshold
        )

        results.append(
            {
                "relative_threshold":
                    SELECTED_RELATIVE_THRESHOLD,

                "absolute_threshold":
                    absolute_threshold,

                "high_records":
                    int(high.sum()),

                "total_records":
                    len(data),

                "high_percent":
                    round(
                        high.mean() * 100,
                        2,
                    ),
            }
        )

    results_df = pd.DataFrame(
        results
    )

    print(
        f"\n{name} combined threshold analysis:"
    )

    print(
        results_df.to_string(
            index=False
        )
    )

    return results_df


# ==========================================================
# SELECTED HOURLY DEFAULTS
# ==========================================================

def evaluate_hourly_defaults(
    data,
    name,
):
    """Evaluate selected hourly DS2 thresholds."""

    valid = data[
        data["observation_count"]
        >= SELECTED_MIN_OBSERVATIONS
    ].copy()

    high = (
        valid["baseline_ratio"]
        >= SELECTED_RELATIVE_THRESHOLD
    ) & (
        valid["pedestrian_count"]
        >= SELECTED_ABSOLUTE_THRESHOLD
    )

    print(
        f"\n{name} selected-default evaluation:"
    )

    print(
        f"Minimum observations : "
        f"{SELECTED_MIN_OBSERVATIONS}"
    )

    print(
        f"Relative threshold   : "
        f"{SELECTED_RELATIVE_THRESHOLD}"
    )

    print(
        f"Absolute threshold   : "
        f"{SELECTED_ABSOLUTE_THRESHOLD}"
    )

    print(
        f"Valid records        : "
        f"{len(valid):,}"
    )

    print(
        f"HIGH records         : "
        f"{int(high.sum()):,}"
    )

    if len(valid) > 0:
        print(
            f"HIGH percentage      : "
            f"{high.mean() * 100:.2f}%"
        )


# ==========================================================
# HOURLY ANALYSIS
# ==========================================================

def run_hourly_analysis(conn):
    """Run complete historical hourly analysis."""

    print("\n========================================")
    print("HOURLY PEDESTRIAN ANALYSIS")
    print("========================================")

    print(
        "\nLoading historical hourly pedestrian data..."
    )

    df = load_hourly_data(
        conn
    )

    print(
        f"Historical hourly records loaded: "
        f"{len(df):,}"
    )

    baseline = calculate_hourly_baseline(
        df
    )

    print(
        f"Hourly baseline slots calculated: "
        f"{len(baseline):,}"
    )

    print(
        f"Sensors represented: "
        f"{baseline['location_id'].nunique()}"
    )

    print(
        "\nFirst 20 hourly baseline records:"
    )

    print(
        baseline.head(20).to_string(
            index=False
        )
    )

    analysis = prepare_analysis(
        df,
        baseline,
        [
            "location_id",
            "day_of_week",
            "hourday",
        ],
    )

    print(
        f"\nRecords used for hourly analysis: "
        f"{len(analysis):,}"
    )

    # All-hour relative analysis.
    analyse_relative_thresholds(
        analysis,
        "All hours",
    )

    # Peak-hour analysis.
    peak = analysis[
        analysis["hourday"].isin(
            PEAK_HOURS
        )
    ].copy()

    analyse_relative_thresholds(
        peak,
        "Peak hours",
    )

    analyse_ratio_distribution(
        analysis,
        "Hourly",
    )

    analyse_observation_requirements(
        baseline,
        "Hourly",
    )

    analyse_absolute_counts(
        analysis,
        "Hourly",
    )

    inspect_extreme_ratios(
        analysis,
        "Hourly",
    )

    # Absolute thresholds apply to hourly data.
    analyse_hourly_combined_thresholds(
        analysis,
        "All hours",
    )

    analyse_hourly_combined_thresholds(
        peak,
        "Peak hours",
    )

    evaluate_hourly_defaults(
        analysis,
        "All hours",
    )

    evaluate_hourly_defaults(
        peak,
        "Peak hours",
    )


# ==========================================================
# MINUTE ANALYSIS
# ==========================================================

def run_minute_analysis(conn):
    """Run exploratory analysis on per-minute pedestrian data."""

    print("\n\n========================================")
    print("PER-MINUTE PEDESTRIAN ANALYSIS")
    print("========================================")

    print(
        "\nLoading per-minute pedestrian data..."
    )

    df = load_minute_data(
        conn
    )

    print(
        f"Minute records loaded: "
        f"{len(df):,}"
    )

    if df.empty:
        print(
            "No per-minute pedestrian data available."
        )

        return

    print(
        f"Sensors represented in minute data: "
        f"{df['location_id'].nunique()}"
    )

    print(
        f"Minute data start: "
        f"{df['sensing_datetime'].min()}"
    )

    print(
        f"Minute data end: "
        f"{df['sensing_datetime'].max()}"
    )

    baseline = calculate_minute_baseline(
        df
    )

    print(
        f"\nMinute baseline slots calculated: "
        f"{len(baseline):,}"
    )

    print(
        "\nFirst 20 minute baseline records:"
    )

    print(
        baseline.head(20).to_string(
            index=False
        )
    )

    print(
        "\nMinute baseline observation-count distribution:"
    )

    print(
        baseline[
            "observation_count"
        ].describe()
    )

    analysis = prepare_analysis(
        df,
        baseline,
        [
            "location_id",
            "day_of_week",
            "hourday",
            "minute",
        ],
    )

    print(
        f"\nRecords used for minute analysis: "
        f"{len(analysis):,}"
    )

    # Relative analysis across all minute readings.
    analyse_relative_thresholds(
        analysis,
        "All minute readings",
    )

    # Minute readings occurring during commuter peak hours.
    peak = analysis[
        analysis["hourday"].isin(
            PEAK_HOURS
        )
    ].copy()

    analyse_relative_thresholds(
        peak,
        "Peak-hour minute readings",
    )

    analyse_ratio_distribution(
        analysis,
        "Per-minute",
    )

    analyse_observation_requirements(
        baseline,
        "Per-minute",
    )

    analyse_absolute_counts(
        analysis,
        "Per-minute",
    )

    inspect_extreme_ratios(
        analysis,
        "Per-minute",
    )

    print(
        "\nNOTE:"
    )

    print(
        "The hourly absolute threshold of "
        f"{SELECTED_ABSOLUTE_THRESHOLD} is not applied "
        "to per-minute readings."
    )

    print(
        "Minute-level absolute thresholds should be "
        "selected separately from the minute data."
    )


# ==========================================================
# MAIN
# ==========================================================

def main():
    """Run hourly and per-minute DS2 threshold analysis."""

    conn = db.connect()

    try:

        run_hourly_analysis(
            conn
        )

        run_minute_analysis(
            conn
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()