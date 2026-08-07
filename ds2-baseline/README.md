# Overview

DS2 builds historical pedestrian baselines and determines default thresholds for identifying unusually congested pedestrian conditions in Melbourne CBD.

The baseline uses historical pedestrian-count data prepared by DS1. Each sensor is compared with its normal pedestrian activity for the same day of the week and hour.

The outputs from DS2 are stored in the shared MySQL database for use by DS3 sensory scoring.

# Files

## `baseline.py`

Calculates and stores historical pedestrian baselines.

For each combination of:

- `location_id`
- `day_of_week`
- `hourday`

the script calculates:

- `average_count`
- `median_count`
- `observation_count`
- `recomputed_at`

The median is used as the main historical baseline because it is less affected by unusual pedestrian spikes.

## `threshold_analysis.py`

Analyses historical pedestrian patterns to determine suitable default congestion thresholds.

The analysis includes:

- Relative threshold comparison
- Peak-hour threshold analysis
- Baseline ratio distribution
- Minimum observation analysis
- Absolute pedestrian-count analysis
- Extreme ratio inspection
- Combined relative and absolute threshold analysis

# Data Source

DS2 reads historical pedestrian data from:

```text
pedestrian_count_hour
```

Required fields:

```text
location_id
day_of_week
hourday
pedestrian_count
```

The current dataset contains:

```text
813,794 historical hourly observations
100 sensors with historical data
```

# Baseline Method

Historical observations are grouped by:

```text
location_id + day_of_week + hourday
```

For example:

```text
Sensor 1
Monday
08:00
```

is treated as a separate baseline from Sensor 1 on Monday at 09:00.

The main baseline is:

```text
median_count = median historical pedestrian count
```

DS2 generated:

```text
16,701 baseline slots
```

Most baseline slots contain approximately 51 to 52 historical observations.

# Relative Threshold Analysis

The relative pedestrian level is calculated as:

```text
baseline_ratio = current pedestrian count / historical median
```

The following thresholds were tested:

| Relative Threshold | All Hours HIGH | Peak Hours HIGH |
|---|---:|---:|
| 1.25 | 20.29% | 14.63% |
| 1.50 | 10.81% | 6.00% |
| 1.75 | 6.61% | 3.08% |
| 2.00 | 4.83% | 1.86% |

The 90th percentile of the historical baseline ratio was approximately:

```text
1.517
```

Based on this result, `1.50` was selected as the default relative threshold.

# Absolute Threshold Analysis

Using only a relative threshold produced misleading results during low-volume periods.

For example:

```text
Historical median = 2
Current count = 4

Ratio = 2.0
```

Although the relative increase is large, four pedestrians do not represent a highly congested corridor.

Historical pedestrian counts showed:

| Percentile | Pedestrian Count |
|---|---:|
| 50th | 162 |
| 75th | 501 |
| 90th | 1,100 |
| 95th | 1,660 |
| 99th | 2,849 |

Absolute thresholds of `250`, `500`, `750`, and `1000` pedestrians per hour were tested together with the selected `1.50` relative threshold.

| Absolute Threshold | All Hours HIGH | Peak Hours HIGH |
|---|---:|---:|
| 250 | 3.17% | 3.34% |
| 500 | 1.96% | 2.07% |
| 750 | 1.31% | 1.40% |
| 1000 | 0.93% | 0.99% |

A default absolute threshold of `500` pedestrians per hour was selected. This is close to the historical 75th percentile and reduces HIGH classifications caused by small historical baselines.

# Minimum Observation Requirement

The following minimum historical observation requirements were evaluated:

| Minimum Observations | Baseline Slots Retained |
|---:|---:|
| 5 | 99.20% |
| 10 | 98.56% |
| 20 | 96.26% |
| 30 | 94.81% |

A minimum of `10` observations was selected.

This retains 98.56% of baseline slots while identifying baselines with limited historical support.

The weak baseline records are not deleted. Their `observation_count` remains available for DS3.

# Selected Default Configuration

The selected DS2 defaults are:

```text
relative_threshold = 1.5
absolute_threshold = 500
minimum_observations = 10
```

These values are stored in the `config` table.

# Database Output

## `baseline`

DS2 populates the following fields:

```text
location_id
day_of_week
hourday
average_count
median_count
observation_count
recomputed_at
```

The table currently contains:

```text
16,701 baseline records
```

The primary key is:

```text
location_id + day_of_week + hourday
```

`baseline.py` uses an upsert so the baseline can be recomputed without creating duplicate records.

## `config`

DS2 stores:

```text
relative_threshold = 1.5
absolute_threshold = 500
minimum_observations = 10
```

DS3 can read these values directly from the database instead of hardcoding them.

# DS3 Handoff

DS2 provides the historical baseline and threshold configuration required by DS3.

The intended scoring logic is:

```text
If observation_count < minimum_observations:
    NO DATA

Else if:
    current pedestrian count >= absolute_threshold
    AND
    current pedestrian count / median_count >= relative_threshold

    HIGH

Else:
    LOW
```

Final implementation of `HIGH`, `LOW`, and `NO DATA` belongs to DS3.

# Running the Baseline

Set the shared database password first.

On macOS/Linux:

```bash
read -s DB_PASSWORD
export DB_PASSWORD
```

Run:

```bash
python3 ds2-baseline/baseline.py
```

The script will:

1. Load historical pedestrian data.
2. Calculate the baseline.
3. Validate observation coverage.
4. Upsert baseline records into MySQL.
5. Store selected configuration values.
6. Verify the database output.

# Running the Threshold Analysis

Run:

```bash
python3 ds2-baseline/threshold_analysis.py
```

This reproduces the analysis used to select the current default thresholds.

# Current DS2 Output

```text
Historical records analysed:       813,794
Sensors with historical data:      100
Baseline slots generated:          16,701
Weak slots (<10 observations):     240

Selected relative threshold:       1.5
Selected absolute threshold:       500
Selected minimum observations:     10

Selected-rule HIGH rate:
All hours:                          1.96%
Peak hours:                         2.07%
```