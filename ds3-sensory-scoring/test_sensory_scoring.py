import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sensory_scoring import (
    HIGH,
    LOW,
    NO_DATA,
    ScoringConfig,
    SensorBaseline,
    SensorLocation,
    SensorReading,
    _sensor_readings_from_sensory_rows,
    match_sensors_to_route,
    melbourne_baseline_slot,
    score_route,
)


class SensoryReadingTableTests(unittest.TestCase):
    def setUp(self):
        self.observed_at = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)

    def test_low_and_high_rows_are_loaded(self):
        readings, covered = _sensor_readings_from_sensory_rows(
            [
                {
                    "location_id": 1,
                    "pedestrian_count": 120,
                    "window_end": self.observed_at,
                    "sensory_status": "Low",
                },
                {
                    "location_id": 2,
                    "pedestrian_count": 850,
                    "window_end": self.observed_at,
                    "sensory_status": "High",
                },
            ]
        )

        self.assertEqual(readings["1"].current_count, 120)
        self.assertEqual(readings["2"].current_count, 850)
        self.assertEqual(covered, {"1", "2"})

    def test_no_data_and_invalid_null_low_high_are_excluded(self):
        readings, covered = _sensor_readings_from_sensory_rows(
            [
                {
                    "location_id": 3,
                    "pedestrian_count": None,
                    "window_end": self.observed_at,
                    "sensory_status": "No Data",
                },
                {
                    "location_id": 4,
                    "pedestrian_count": None,
                    "window_end": self.observed_at,
                    "sensory_status": "Low",
                },
                {
                    "location_id": 5,
                    "pedestrian_count": None,
                    "window_end": self.observed_at,
                    "sensory_status": "High",
                },
            ]
        )

        self.assertEqual(readings, {})
        self.assertEqual(covered, {"3", "4", "5"})


class SensorMatchingTests(unittest.TestCase):
    def test_matches_sensor_inside_buffer_and_excludes_outside(self):
        route = [[-37.814, 144.963], [-37.810, 144.963]]
        sensors = [
            SensorLocation("near", -37.812, 144.9635),
            SensorLocation("far", -37.812, 144.9700),
        ]
        self.assertEqual(match_sensors_to_route(route, sensors, 120), ["near"])

    def test_invalid_or_short_route_has_no_matches(self):
        sensor = SensorLocation("1", -37.812, 144.963)
        self.assertEqual(match_sensors_to_route([], [sensor]), [])
        self.assertEqual(match_sensors_to_route([[-37.812, 144.963]], [sensor]), [])


class RouteScoringTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc)
        self.config = ScoringConfig()

    def score(self, ids, readings, baselines):
        return score_route(ids, readings, baselines, self.config, self.now)[0]

    def test_too_few_sensors_is_no_data(self):
        self.assertEqual(self.score([], {}, {}), NO_DATA)

    def test_missing_live_record_is_no_data(self):
        baseline = {"1": SensorBaseline("1", 300, 20)}
        self.assertEqual(self.score(["1"], {}, baseline), NO_DATA)

    def test_too_few_baseline_observations_is_no_data(self):
        readings = {"1": SensorReading("1", 600, self.now)}
        baselines = {"1": SensorBaseline("1", 300, 9)}
        self.assertEqual(self.score(["1"], readings, baselines), NO_DATA)

    def test_stale_live_record_is_no_data(self):
        readings = {"1": SensorReading("1", 600, self.now - timedelta(minutes=31))}
        baselines = {"1": SensorBaseline("1", 300, 20)}
        self.assertEqual(self.score(["1"], readings, baselines), NO_DATA)

    def test_unknown_live_observation_time_is_no_data(self):
        readings = {"1": SensorReading("1", 600, None)}
        baselines = {"1": SensorBaseline("1", 300, 20)}
        self.assertEqual(self.score(["1"], readings, baselines), NO_DATA)

    def test_naive_database_timestamp_is_interpreted_as_utc(self):
        naive_utc = datetime(2026, 8, 9, 1, 45, tzinfo=timezone.utc).replace(tzinfo=None)
        readings = {"1": SensorReading("1", 600, naive_utc)}
        baselines = {"1": SensorBaseline("1", 300, 20)}
        self.assertEqual(self.score(["1"], readings, baselines), HIGH)

    def test_relative_threshold_alone_is_low(self):
        readings = {"1": SensorReading("1", 40, self.now)}
        baselines = {"1": SensorBaseline("1", 20, 20)}
        self.assertEqual(self.score(["1"], readings, baselines), LOW)

    def test_absolute_threshold_is_high(self):
        readings = {
            "1": SensorReading(
                sensor_id="1",
                current_count=700;
                observed_at=self.now,
            )
        }

        baselines = {
            "1": SensorBaseline(
                sensor_id="1",
                median_count=1000,
                observation_count=20,
            )
        }

        self.assertEqual(
            self.score(["1"], readings, baselines),
            HIGH,
        )

    def test_both_thresholds_is_high(self):
        readings = {"1": SensorReading("1", 600, self.now)}
        baselines = {"1": SensorBaseline("1", 300, 20)}
        status, notification = score_route(["1"], readings, baselines, self.config, self.now)
        self.assertEqual(status, HIGH)
        self.assertIsNotNone(notification)

    def test_any_high_sensor_makes_route_high(self):
        readings = {
            "1": SensorReading("1", 200, self.now),
            "2": SensorReading("2", 900, self.now),
        }
        baselines = {
            "1": SensorBaseline("1", 200, 20),
            "2": SensorBaseline("2", 400, 20),
        }
        self.assertEqual(self.score(["1", "2"], readings, baselines), HIGH)


class BaselineTimezoneTests(unittest.TestCase):
    def test_utc_time_is_converted_to_melbourne_slot(self):
        # 2026-08-08 16:30 UTC is 2026-08-09 02:30 in Melbourne (UTC+10),
        # crossing both the date and weekday boundary.
        utc_time = datetime(2026, 8, 8, 16, 30, tzinfo=timezone.utc)
        self.assertEqual(melbourne_baseline_slot(utc_time), (6, 2))

    def test_naive_supplied_time_is_treated_as_melbourne_local(self):
        local_time = datetime(2026, 8, 9, 23, 30, tzinfo=timezone.utc).replace(tzinfo=None)
        self.assertEqual(melbourne_baseline_slot(local_time), (6, 23))


if __name__ == "__main__":
    unittest.main()
