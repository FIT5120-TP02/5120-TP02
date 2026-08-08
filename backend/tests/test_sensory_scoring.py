"""
Tests for app/services/sensory_scoring.py.

Code Quality slide requirement: "Sensory scoring logic must have tests."
Covers every branch of the NO DATA rule set plus the LOW/HIGH threshold,
since a wrong LOW/HIGH is a safety issue per the Security Plan slide.
"""

from app.services.sensory_scoring import (
    HIGH,
    LOW,
    NO_DATA,
    SensorBaseline,
    SensorReading,
    score_route,
)


def test_no_sensors_matched_returns_no_data():
    status, notification = score_route([], {}, {})
    assert status == NO_DATA
    assert notification is None


def test_no_baseline_observations_returns_no_data():
    status, _ = score_route(
        ["s1"],
        {"s1": SensorReading("s1", 50)},
        {"s1": SensorBaseline("s1", median_count=60, observation_count=2)},  # below min
    )
    assert status == NO_DATA


def test_baseline_exists_but_no_live_reading_returns_no_data():
    status, _ = score_route(
        ["s1"],
        {},  # no current reading
        {"s1": SensorBaseline("s1", median_count=60, observation_count=30)},
    )
    assert status == NO_DATA


def test_current_below_threshold_returns_low():
    status, notification = score_route(
        ["s1"],
        {"s1": SensorReading("s1", 40)},
        {"s1": SensorBaseline("s1", median_count=60, observation_count=30)},
    )
    assert status == LOW
    assert notification is None


def test_current_at_or_above_threshold_returns_high_with_notification():
    # default multiplier is 1.5x -> threshold = 90
    status, notification = score_route(
        ["s1"],
        {"s1": SensorReading("s1", 95)},
        {"s1": SensorBaseline("s1", median_count=60, observation_count=30)},
    )
    assert status == HIGH
    assert notification is not None
    assert "above" in notification.lower()


def test_multiple_matched_sensors_are_averaged():
    status, _ = score_route(
        ["s1", "s2"],
        {"s1": SensorReading("s1", 30), "s2": SensorReading("s2", 30)},
        {
            "s1": SensorBaseline("s1", median_count=60, observation_count=30),
            "s2": SensorBaseline("s2", median_count=60, observation_count=30),
        },
    )
    assert status == LOW


def test_zero_baseline_is_treated_as_no_data_not_divide_by_zero():
    status, _ = score_route(
        ["s1"],
        {"s1": SensorReading("s1", 10)},
        {"s1": SensorBaseline("s1", median_count=0, observation_count=30)},
    )
    assert status == NO_DATA


def test_mismatched_sensor_sets_never_get_compared():
    # Reading only exists for s1, baseline only exists for s2 - before the
    # fix, both "usable" lists were non-empty independently and got
    # averaged and compared anyway, comparing unrelated sensors.
    status, notification = score_route(
        ["s1", "s2"],
        {"s1": SensorReading("s1", 999)},  # only a reading, no baseline
        {
            "s2": SensorBaseline("s2", median_count=10, observation_count=30)
        },  # only a baseline, no reading
    )
    assert status == NO_DATA
    assert notification is None


def test_partial_overlap_only_uses_sensors_with_both_reading_and_baseline():
    # s1 has both reading and baseline (usable); s2 only has a reading.
    # Only s1 should be used - if s2 leaked in, the average would be
    # dragged toward s2's very high reading and wrongly return HIGH.
    status, _ = score_route(
        ["s1", "s2"],
        {
            "s1": SensorReading("s1", 30),
            "s2": SensorReading("s2", 999),
        },
        {
            "s1": SensorBaseline("s1", median_count=60, observation_count=30),
        },
    )
    assert status == LOW
