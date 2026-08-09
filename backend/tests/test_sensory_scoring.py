"""
Tests for app/services/sensory_scoring.py.

Ported verbatim from DS3's approved test suite (PR #4,
`ds3-sensory-scoring/test_sensory_scoring.py`) - only the import path
changed (`from sensory_scoring import ...` with a sys.path hack, since
DS3's original was a standalone script sibling to the module, to
`from app.services.sensory_scoring import ...` to match this package's
layout - no test bodies changed).

Code Quality slide requirement: "Sensory scoring logic must have tests."
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.services.sensory_scoring import (
    HIGH,
    LOW,
    NO_DATA,
    ScoringConfig,
    SensorBaseline,
    SensorLocation,
    SensorReading,
    match_sensors_to_route,
    melbourne_baseline_slot,
    score_route,
)


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

    def test_absolute_threshold_alone_is_low(self):
        readings = {"1": SensorReading("1", 500, self.now)}
        baselines = {"1": SensorBaseline("1", 400, 20)}
        self.assertEqual(self.score(["1"], readings, baselines), LOW)

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
