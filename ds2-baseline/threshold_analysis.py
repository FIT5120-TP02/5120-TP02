import sys
from pathlib import Path

import pandas as pd

# Allow this file to import db.py from the project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import db


# Candidate relative thresholds to test
THRESHOLDS = [1.25, 1.50, 1.75, 2.00]


def load_hourly_data(conn):
    """
    Load historical hourly pedestrian counts from MySQL.
    """

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

    # Ensure numeric values
    df["location_id"] = pd.to_numeric(df["location_id"])
    df["day_of_week"] = pd.to_numeric(df["day_of_week"])
    df["hourday"] = pd.to_numeric(df["hourday"])
    df["pedestrian_count"] = pd.to_numeric(
        df["pedestrian_count"]
    )

    return df


def calculate_baseline(df):
    """
    Calculate normal pedestrian activity for every:

    sensor × day of week × hour

    Median is used because it is less affected by unusual
    spikes such as events or disruptions.
    """

    baseline = (
        df.groupby(
            [
                "location_id",
                "day_of_week",
                "hourday"
            ]
        )
        .agg(
            median_count=(
                "pedestrian_count",
                "median"
            ),
            observation_count=(
                "pedestrian_count",
                "size"
            )
        )
        .reset_index()
    )

    return baseline


def prepare_analysis(df, baseline):
    """
    Attach each historical observation to its corresponding
    historical baseline.

    baseline_ratio:

        pedestrian_count / median_count

    Example:

        current = 1500
        median = 1000

        ratio = 1.5
    """

    data = df.merge(
        baseline,
        on=[
            "location_id",
            "day_of_week",
            "hourday"
        ],
        how="left"
    )

    # Cannot calculate meaningful ratio when median is zero
    data = data[
        data["median_count"] > 0
    ].copy()

    data["baseline_ratio"] = (
        data["pedestrian_count"]
        / data["median_count"]
    )

    return data


def analyse_thresholds(data, name):
    """
    Test candidate threshold multipliers.

    Example:

        threshold = 1.5

        HIGH when:

        current pedestrian count >= 1.5 × historical median
    """

    results = []

    for threshold in THRESHOLDS:

        high = (
            data["baseline_ratio"]
            >= threshold
        )

        results.append({
            "threshold": threshold,
            "high_records": int(high.sum()),
            "total_records": len(data),
            "high_percent": round(
                high.mean() * 100,
                2
            )
        })

    results_df = pd.DataFrame(results)

    print(f"\n{name}:")
    print(
        results_df.to_string(
            index=False
        )
    )

    return results_df


def ratio_summary(data):
    """
    Examine how pedestrian counts vary relative to their
    historical baseline.
    """

    print("\nBaseline ratio distribution:")

    summary = (
        data["baseline_ratio"]
        .describe(
            percentiles=[
                0.50,
                0.75,
                0.90,
                0.95,
                0.99
            ]
        )
    )

    print(summary)


def observation_rule_analysis(baseline):
    """
    Test possible minimum historical observation requirements.

    This helps DS3 later decide when there is not enough
    historical information to calculate a reliable score.
    """

    print("\nMinimum observation analysis:")

    for minimum in [
        5,
        10,
        20,
        30
    ]:

        valid = (
            baseline["observation_count"]
            >= minimum
        )

        retained = valid.sum()

        percent = (
            valid.mean() * 100
        )

        print(
            f"Minimum {minimum:2d}: "
            f"{retained:,} / "
            f"{len(baseline):,} "
            f"({percent:.2f}%) retained"
        )


def absolute_count_analysis(data):
    """
    Check actual pedestrian volumes.

    A relative ratio alone can be misleading.

    Example:

        baseline = 2
        current = 4
        ratio = 2.0

    The ratio is high, but four pedestrians does not represent
    a highly congested corridor.
    """

    print(
        "\nAbsolute pedestrian count distribution:"
    )

    overall = (
        data["pedestrian_count"]
        .describe(
            percentiles=[
                0.50,
                0.75,
                0.90,
                0.95,
                0.99
            ]
        )
    )

    print(overall)

    # Examine actual counts currently captured by our
    # candidate 1.5 relative threshold
    high_ratio = data[
        data["baseline_ratio"] >= 1.5
    ]

    print(
        "\nPedestrian counts where "
        "baseline ratio >= 1.5:"
    )

    high_summary = (
        high_ratio[
            "pedestrian_count"
        ]
        .describe(
            percentiles=[
                0.10,
                0.25,
                0.50,
                0.75,
                0.90,
                0.95,
                0.99
            ]
        )
    )

    print(high_summary)


def inspect_extreme_ratios(data):
    """
    Inspect unusually large ratios.

    This helps identify cases where a very small baseline
    causes an unrealistic relative congestion score.
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
                "baseline_ratio"
            ]
        ]
        .sort_values(
            "baseline_ratio",
            ascending=False
        )
        .head(20)
    )

    print(
        "\nTop 20 baseline ratios:"
    )

    print(
        extreme.to_string(
            index=False
        )
    )


if __name__ == "__main__":

    conn = db.connect()

    # --------------------------------
    # Step 1
    # Load historical data
    # --------------------------------

    print(
        "Loading historical pedestrian data..."
    )

    df = load_hourly_data(conn)

    print(
        f"Historical records loaded: "
        f"{len(df):,}"
    )

    # --------------------------------
    # Step 2
    # Calculate baseline
    # --------------------------------

    baseline = calculate_baseline(df)

    print(
        f"Baseline slots calculated: "
        f"{len(baseline):,}"
    )

    # --------------------------------
    # Step 3
    # Match observations to baseline
    # --------------------------------

    analysis = prepare_analysis(
        df,
        baseline
    )

    print(
        f"Records used for threshold analysis: "
        f"{len(analysis):,}"
    )

    # --------------------------------
    # Step 4
    # Analyse all hours
    # --------------------------------

    analyse_thresholds(
        analysis,
        "All hours"
    )

    # --------------------------------
    # Step 5
    # Analyse peak periods
    # --------------------------------

    peak = analysis[
        analysis[
            "hourday"
        ].isin(
            [
                7,
                8,
                9,
                16,
                17,
                18
            ]
        )
    ]

    analyse_thresholds(
        peak,
        "Peak hours"
    )

    # --------------------------------
    # Step 6
    # Ratio distribution
    # --------------------------------

    ratio_summary(
        analysis
    )

    # --------------------------------
    # Step 7
    # Historical observation coverage
    # --------------------------------

    observation_rule_analysis(
        baseline
    )

    # --------------------------------
    # Step 8
    # Absolute pedestrian counts
    # --------------------------------

    absolute_count_analysis(
        analysis
    )

    # --------------------------------
    # Step 9
    # Investigate extreme ratios
    # --------------------------------

    inspect_extreme_ratios(
        analysis
    )

    conn.close()