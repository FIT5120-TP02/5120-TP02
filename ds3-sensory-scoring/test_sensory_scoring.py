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
    match_sensors_to_route,
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
        status, notification = score_route(
            ["1"], readings, baselines, self.config, self.now
        )
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


if __name__ == "__main__":
    unittest.main()
