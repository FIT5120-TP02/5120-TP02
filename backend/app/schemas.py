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
    # Representative sensor behind sensory_status - see
    # app/routers/routes.py::_representative_sensor for the selection rule.
    # None when no matched sensor has usable data (sensory_status == "NO DATA").
    sensory_value: float | None = None  # DS's "pedestrian_count" - the raw current reading
    # Nearest real street address to that sensor, e.g. "23 Mackenzie St,
    # Melbourne" - resolved against DS's separate `address` table (see
    # app/routers/routes.py::_nearest_address), NOT `location.address`
    # (that column exists but has never been populated for any row). Can
    # be None even when there IS a representative sensor, if nothing in
    # the `address` table falls within the search radius of it.
    address_pnt: str | None = None
    pedestrian_per_min: float | None = None  # same reading as sensory_value, for display
    # Trailing 60-minute total for that same sensor, summed live from
    # pedestrian_count_minute (see routes.py::_latest_hourly_counts) - NOT
    # DS1's pedestrian_count_hour archive, which is batch-loaded roughly
    # daily and was previously found to drift out of sync with
    # pedestrian_per_min (e.g. "49/min but 21/hour" for the same sensor).
    pedestrian_per_hour: float | None = None


class RouteCompareResponse(BaseModel):
    routes: list[RouteOption]
    generated_at: datetime


# ---------- Sensory refuge locations (US 2.1) ----------
class RefugeLocationOut(BaseModel):
    location_id: int
    name: str
    category: str
    # DS-confirmed against the live DB: location.address has a real street
    # address (with number) for 79/92 refuge rows - null for the rest, and
    # always null for non-refuge rows. `name` (location_name) is the
    # fallback used whenever address is null, so this field is never empty.
    address: str
    eta_min: float
    lat: float
    lng: float


class RefugeListResponse(BaseModel):
    refuges: list[RefugeLocationOut]
    generated_at: datetime
