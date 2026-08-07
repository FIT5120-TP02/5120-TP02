import sys
from pathlib import Path

import pandas as pd


# Add the project root so this script can import the shared db.py.
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import db


# Thresholds evaluated during exploratory analysis.
RELATIVE_THRESHOLDS = [1.25, 1.50, 1.75, 2.00]
ABSOLUTE_THRESHOLDS = [250, 500, 750, 1000]

# Selected default values based on the historical analysis.
SELECTED_RELATIVE_THRESHOLD = 1.50
SELECTED_ABSOLUTE_THRESHOLD = 500
SELECTED_MIN_OBSERVATIONS = 10

# Peak periods used to separately evaluate commuter-hour behaviour.
PEAK_HOURS = [7, 8, 9, 16, 17, 18]


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

    # Explicit conversion protects the analysis from unexpected string values.
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
    Calculate the normal pedestrian level for each sensor, weekday and hour.

    The median is used instead of the mean because it is less affected by
    occasional unusually large pedestrian-count spikes.
    """

    return (
        df.groupby(
            ["location_id", "day_of_week", "hourday"]
        )
        .agg(
            median_count=("pedestrian_count", "median"),
            observation_count=("pedestrian_count", "size"),
        )
        .reset_index()
    )


def prepare_analysis(df, baseline):
    """
    Join each historical observation to its corresponding baseline and calculate
    how large the observation is relative to normal activity.

        baseline_ratio = pedestrian_count / historical median
    """

    data = df.merge(
        baseline,
        on=["location_id", "day_of_week", "hourday"],
        how="left",
    )

    # A zero median cannot produce a meaningful relative ratio.
    data = data[data["median_count"] > 0].copy()

    data["baseline_ratio"] = (
        data["pedestrian_count"] / data["median_count"]
    )

    return data


def analyse_relative_thresholds(data, name):
    """Compare candidate relative thresholds."""

    results = []

    for threshold in RELATIVE_THRESHOLDS:
        high = data["baseline_ratio"] >= threshold

        results.append(
            {
                "threshold": threshold,
                "high_records": int(high.sum()),
                "total_records": len(data),
                "high_percent": round(high.mean() * 100, 2),
            }
        )

    results_df = pd.DataFrame(results)

    print(f"\n{name} relative threshold analysis:")
    print(results_df.to_string(index=False))

    return results_df


def analyse_ratio_distribution(data):
    """Show how observations are distributed relative to their baselines."""

    print("\nBaseline ratio distribution:")

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


def analyse_observation_requirements(baseline):
    """
    Compare possible minimum observation requirements.

    A baseline based on only a few historical records is less reliable than a
    baseline based on many weeks of observations.
    """

    print("\nMinimum observation analysis:")

    for minimum in [5, 10, 20, 30]:
        valid = baseline["observation_count"] >= minimum

        print(
            f"Minimum {minimum:2d}: "
            f"{valid.sum():,} / {len(baseline):,} "
            f"({valid.mean() * 100:.2f}%) retained"
        )


def analyse_absolute_counts(data):
    """
    Examine actual pedestrian volumes.

    A relative threshold alone can incorrectly flag low-volume periods. For
    example, increasing from 2 to 4 pedestrians gives a ratio of 2.0 even though
    the absolute pedestrian volume remains very low.
    """

    print("\nAbsolute pedestrian count distribution:")

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
        data["baseline_ratio"] >= SELECTED_RELATIVE_THRESHOLD
    ]

    print(
        "\nPedestrian counts where "
        f"baseline ratio >= {SELECTED_RELATIVE_THRESHOLD}:"
    )

    print(
        relative_high["pedestrian_count"].describe(
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


def inspect_extreme_ratios(data, limit=20):
    """
    Display the largest baseline ratios.

    This helps identify cases where extremely small historical medians produce
    very large relative ratios.
    """

    extreme = (
        data[
            [
                "location_id",
                "day_of_week",
                "hourday",
                "pedestrian_count",
                "median_count",
                "observation_count",
                "baseline_ratio",
            ]
        ]
        .sort_values("baseline_ratio", ascending=False)
        .head(limit)
    )

    print(f"\nTop {limit} baseline ratios:")
    print(extreme.to_string(index=False))


def analyse_combined_thresholds(data, name):
    """
    Compare absolute thresholds while keeping the selected relative threshold.

    Candidate HIGH condition:

        baseline_ratio >= 1.50
        AND
        pedestrian_count >= absolute threshold
    """

    results = []

    for absolute_threshold in ABSOLUTE_THRESHOLDS:
        high = (
            data["baseline_ratio"] >= SELECTED_RELATIVE_THRESHOLD
        ) & (
            data["pedestrian_count"] >= absolute_threshold
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
                    round(high.mean() * 100, 2),
            }
        )

    results_df = pd.DataFrame(results)

    print(f"\n{name} combined threshold analysis:")
    print(results_df.to_string(index=False))

    return results_df


def evaluate_selected_defaults(data, name):
    """
    Evaluate the selected DS2 default settings.

    Records with fewer than the selected number of historical observations are
    excluded because their baselines are considered insufficiently supported.
    """

    valid = data[
        data["observation_count"] >= SELECTED_MIN_OBSERVATIONS
    ].copy()

    high = (
        valid["baseline_ratio"] >= SELECTED_RELATIVE_THRESHOLD
    ) & (
        valid["pedestrian_count"] >= SELECTED_ABSOLUTE_THRESHOLD
    )

    print(f"\n{name} selected-default evaluation:")
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
    print(
        f"HIGH percentage      : "
        f"{high.mean() * 100:.2f}%"
    )


def main():
    """Run the complete DS2 threshold analysis."""

    conn = db.connect()

    try:
        print("Loading historical pedestrian data...")

        df = load_hourly_data(conn)

        print(
            f"Historical records loaded: "
            f"{len(df):,}"
        )

        baseline = calculate_baseline(df)

        print(
            f"Baseline slots calculated: "
            f"{len(baseline):,}"
        )

        analysis = prepare_analysis(
            df,
            baseline,
        )

        print(
            f"Records used for threshold analysis: "
            f"{len(analysis):,}"
        )

        # Compare candidate relative thresholds across all observations.
        analyse_relative_thresholds(
            analysis,
            "All hours",
        )

        # Analyse peak periods separately because the product specifically
        # supports commuters travelling during peak hours.
        peak = analysis[
            analysis["hourday"].isin(PEAK_HOURS)
        ].copy()

        analyse_relative_thresholds(
            peak,
            "Peak hours",
        )

        # Examine the distributions behind the threshold decisions.
        analyse_ratio_distribution(analysis)

        analyse_observation_requirements(
            baseline
        )

        analyse_absolute_counts(
            analysis
        )

        inspect_extreme_ratios(
            analysis
        )

        # Test whether combining relative and absolute thresholds avoids
        # incorrectly classifying very small pedestrian counts as HIGH.
        analyse_combined_thresholds(
            analysis,
            "All hours",
        )

        analyse_combined_thresholds(
            peak,
            "Peak hours",
        )

        # Report the currently selected defaults.
        evaluate_selected_defaults(
            analysis,
            "All hours",
        )

        evaluate_selected_defaults(
            peak,
            "Peak hours",
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()