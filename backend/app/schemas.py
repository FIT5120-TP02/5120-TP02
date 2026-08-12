"""
Pydantic request/response schemas for the REST API.

No account/auth schemas here - per team decision (privacy: no user login),
this is an anonymous, no-account public API. Every request is
self-contained; nothing is scoped to a signed-in user.
"""

from datetime import datetime

from pydantic import BaseModel


# ---------- Routes (US 1.1 / US 1.2) ----------
class RouteCompareRequest(BaseModel):
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float


class AddressPoint(BaseModel):
    """Lat/lng of the sensor behind a route's sensory reading (for map icons)."""

    lat: float
    lng: float


class RouteOption(BaseModel):
    """One candidate route as shown on the Route comparison screen."""

    route_id: str
    label: str  # e.g. "Via Flinders Lane"
    distance_km: float
    duration_min: float
    sensory_status: str  # "LOW" | "HIGH" | "NO DATA"
    geometry: list[list[float]]  # [[lat, lng], ...] polyline points
    avoided_corridor: str | None = None
    notification: str | None = None  # text notification per US 1.2
    # Representative sensor behind sensory_status - the matched sensor with
    # the highest current reading. None when no matched sensor has data
    # (sensory_status == "NO DATA").
    sensory_value: float | None = None  # DS's "pedestrian_count" - the raw current reading
    address_pnt: AddressPoint | None = None  # location of that sensor
    pedestrian_per_min: float | None = None  # same reading as sensory_value, for display
    pedestrian_per_hour: float | None = None  # latest hourly aggregate for that same sensor


class RouteCompareResponse(BaseModel):
    routes: list[RouteOption]
    generated_at: datetime


# ---------- Sensory refuge locations (US 2.1) ----------
class RefugeLocationOut(BaseModel):
    location_id: int
    name: str
    category: str
    eta_min: float
    lat: float
    lng: float


class RefugeListResponse(BaseModel):
    refuges: list[RefugeLocationOut]
    generated_at: datetime
