# DS3 — Sensory scoring

This directory implements the DS3 responsibility without modifying DS1, DS2,
or the backend.

## What it does

1. Matches sensor locations to a route polyline using a configurable buffer
   radius (120 m by default).
2. Selects the latest DS1 live reading for every matched sensor.
3. Selects the DS2 baseline for the current Melbourne weekday and hour.
4. Returns `LOW`, `HIGH`, or `NO DATA`.

## Rules

`NO DATA` is returned when:

- fewer than `minimum_route_sensors` sensors match the route;
- any matched sensor has no live reading;
- a live reading has no observation timestamp;
- a live reading is older than `live_max_age_minutes`;
- any matched sensor has no baseline for the current slot;
- a baseline has fewer than `minimum_observations`; or
- a baseline/count is invalid.

`HIGH` requires at least one matched sensor to satisfy both DS2 rules:

```text
current_count >= absolute_threshold
current_count >= median_count * relative_threshold
```

If the data is complete and no sensor is HIGH, the result is `LOW`.

DS1's naive MySQL `sensing_datetime` values are interpreted as UTC, matching
the schema documentation. Baseline weekday/hour selection is always converted
to `Australia/Melbourne`, including when callers supply a UTC timestamp.

DS2's database keys are used when present. Optional DS3 configuration keys
fall back to these values:

| Key | Default |
|---|---:|
| `route_buffer_radius_m` | 120 |
| `relative_threshold` | 1.5 |
| `absolute_threshold` | 500 |
| `minimum_observations` | 10 |
| `minimum_route_sensors` | 1 |
| `live_max_age_minutes` | 30 |

## Usage

Install the database driver first:

```bash
python -m pip install -r requirements.txt
```

The route geometry must use the backend's `[[latitude, longitude], ...]`
format:

```python
import db
from sensory_scoring import score_route_from_database

route = [
    [-37.814, 144.963],
    [-37.810, 144.963],
]

conn = db.connect()
try:
    status, notification = score_route_from_database(route, conn)
finally:
    conn.close()
```

When run directly, the program prompts for the database password if
`DB_PASSWORD` is not already set. The input is visible but is not saved.

## Tests

The unit tests do not access the shared database:

```bash
python -m unittest discover -s ds3-sensory-scoring -p "test_*.py" -v
```
