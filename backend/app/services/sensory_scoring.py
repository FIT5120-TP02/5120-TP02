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
    """
    settings = get_settings()

    if len(matched_sensor_ids) == 0:
        return NO_DATA, None

    usable_baselines = [
        baselines[sid]
        for sid in matched_sensor_ids
        if sid in baselines and baselines[sid].observation_count >= settings.min_baseline_observations
    ]
    if not usable_baselines:
        return NO_DATA, None

    usable_readings = [readings[sid] for sid in matched_sensor_ids if sid in readings]
    if not usable_readings:
        return NO_DATA, None

    avg_current = sum(r.current_count for r in usable_readings) / len(usable_readings)
    avg_baseline = sum(b.median_count for b in usable_baselines) / len(usable_baselines)

    if avg_baseline <= 0:
        return NO_DATA, None

    threshold = avg_baseline * settings.crowd_high_threshold_multiplier
    if avg_current >= threshold:
        return HIGH, "This corridor is above your usual density threshold right now."
    return LOW, None
