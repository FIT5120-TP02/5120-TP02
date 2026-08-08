"""Pydantic request/response schemas for the REST API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- Auth ----------
class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Preferences ----------
class PreferenceIn(BaseModel):
    noise_tolerance: float | None = None
    light_tolerance: float | None = None
    crowd_tolerance: float | None = None
    preferred_route_type: str | None = None


class PreferenceOut(PreferenceIn):
    model_config = ConfigDict(from_attributes=True)
    preference_id: int
    user_id: int


# ---------- Routes (US 1.1 / US 1.2) ----------
class RouteCompareRequest(BaseModel):
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float
    preference_id: int | None = None


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
