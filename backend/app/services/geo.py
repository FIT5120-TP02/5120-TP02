"""Shared geo helper - haversine distance, used by refuges.py (distance to
a refuge). Route<->sensor proximity matching now uses DS3's own
point-to-segment implementation in app/services/sensory_scoring.py
instead of a second, separate one here."""

from __future__ import annotations

import math


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
