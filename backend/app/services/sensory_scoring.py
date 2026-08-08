"""
Sensory scoring: assigns LOW / HIGH / NO DATA to a candidate route.

Ownership note (see Build Roles slide): DS3 owns this logic long-term -
matching sensors to a route by buffer radius, comparing current vs
baseline, and the NO DATA rules. This module is IT's placeholder so the
REST API has a real, working implementation to call and test against
from day one. When DS3's version lands, swap the body of
`score_route()` for their function and keep the signature so the
routers/routes.py caller doesn't need to change.

Safety note from the Security Plan: "A false LOW sends a sensory-sensitive
user into exactly what they're avoiding - NO DATA is a safety control, not
a data gap." So this function must never guess a LOW/HIGH when the
underlying data doesn't support it - it must return "NO DATA" instead.
This includes never comparing a reading from one sensor against a
baseline from a different sensor - only sensors with BOTH a usable
baseline and a live reading are compared, on the intersection of the two.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings

LOW = "LOW"
HIGH = "HIGH"
NO_DATA = "NO DATA"


@dataclass
class SensorReading:
    sensor_id: str
    current_count: float


@dataclass
class SensorBaseline:
    sensor_id: str
    median_count: float
    observation_count: int


def score_route(
    matched_sensor_ids: list[str],
    readings: dict[str, SensorReading],
    baselines: dict[str, SensorBaseline],
) -> tuple[str, str | None]:
    """
    Returns (status, notification_text).

    NO DATA rules (per DS3's ownership on the Build Roles slide):
      1. Too few sensors matched to the route buffer.
      2. Too few baseline observations for the matched sensors.
      3. No live reading available for the matched sensors right now.
      4. No sensor has BOTH a usable baseline and a live reading - a
         reading for sensor A must never be compared against sensor B's
         baseline just because both individually looked "usable".
    """
    settings = get_settings()

    if len(matched_sensor_ids) == 0:
        return NO_DATA, None

    # Only sensors with both a sufficiently-observed baseline AND a live
    # reading right now are usable - the intersection, not two independent
    # lists that might not actually refer to the same sensors.
    usable_sensor_ids = [
        sid
        for sid in matched_sensor_ids
        if sid in baselines
        and baselines[sid].observation_count >= settings.min_baseline_observations
        and sid in readings
    ]
    if not usable_sensor_ids:
        return NO_DATA, None

    avg_current = sum(readings[sid].current_count for sid in usable_sensor_ids) / len(
        usable_sensor_ids
    )
    avg_baseline = sum(baselines[sid].median_count for sid in usable_sensor_ids) / len(
        usable_sensor_ids
    )

    if avg_baseline <= 0:
        return NO_DATA, None

    threshold = avg_baseline * settings.crowd_high_threshold_multiplier
    if avg_current >= threshold:
        return HIGH, "This corridor is above your usual density threshold right now."
    return LOW, None
