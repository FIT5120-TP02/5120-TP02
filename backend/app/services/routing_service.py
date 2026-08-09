"""
Routing service integration (IT's responsibility per the onboarding plan:
"Routing service integration").

Design goal: the rest of the backend never talks to OSRM/GraphHopper/etc.
directly - it calls get_candidate_routes() and gets back a provider-neutral
shape. Swap ROUTING_PROVIDER in .env once the team picks a concrete free-tier
routing service, and only this file needs to change.

Candidates evaluated for the free tier (see README for notes):
  - OSRM: self-hosted, no request cap, but you host the Docker container.
  - OpenRouteService: hosted free tier, rate-limited (2000 req/day).
  - GraphHopper: hosted free tier, rate-limited.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class CandidateRoute:
    route_id: str
    label: str
    distance_km: float
    duration_min: float
    geometry: list[list[float]]  # [[lat, lng], ...]


def get_candidate_routes(
    origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float
) -> list[CandidateRoute]:
    settings = get_settings()

    if settings.routing_provider == "mock":
        return _mock_candidate_routes(origin_lat, origin_lng, destination_lat, destination_lng)

    if settings.routing_provider == "osrm":
        return _osrm_candidate_routes(origin_lat, origin_lng, destination_lat, destination_lng)

    if settings.routing_provider == "openrouteservice":
        return _ors_candidate_routes(origin_lat, origin_lng, destination_lat, destination_lng)

    raise NotImplementedError(
        f"Routing provider '{settings.routing_provider}' is not wired up yet. "
        "Add a branch here once the team confirms the free-tier service."
    )


_ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/foot-walking/geojson"


def _ors_candidate_routes(
    origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float
) -> list[CandidateRoute]:
    """
    OpenRouteService (hosted, free tier - 2000 req/day, 40 req/min as of
    writing). Chosen over self-hosted OSRM because it needs no server to
    run/maintain - just a free API key from openrouteservice.org.

    Set ROUTING_PROVIDER=openrouteservice and ROUTING_SERVICE_API_KEY in
    .env to use this.

    Note: alternative_routes is best-effort - ORS may return fewer than
    target_count alternatives for the foot-walking profile depending on the
    area/distance, so callers should not assume exactly 3 routes back (the
    `mock` provider is what guarantees exactly 3, for frontend dev/demo).
    """
    settings = get_settings()
    if not settings.routing_service_api_key:
        raise RuntimeError(
            "ROUTING_SERVICE_API_KEY is not set. Get a free key at "
            "https://openrouteservice.org/dev/#/signup and set it in .env."
        )

    body = {
        "coordinates": [[origin_lng, origin_lat], [destination_lng, destination_lat]],
        "alternative_routes": {"target_count": 3, "share_factor": 0.6, "weight_factor": 1.4},
    }
    headers = {
        "Authorization": settings.routing_service_api_key,
        "Content-Type": "application/json",
    }
    response = httpx.post(_ORS_BASE_URL, json=body, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    routes: list[CandidateRoute] = []
    for i, feature in enumerate(data.get("features", [])):
        coords = feature["geometry"]["coordinates"]  # [[lng, lat], ...]
        summary = feature["properties"]["summary"]
        routes.append(
            CandidateRoute(
                route_id=f"ors-{i}",
                label=f"Route {i + 1}",
                distance_km=round(summary["distance"] / 1000, 2),
                duration_min=round(summary["duration"] / 60, 1),
                geometry=[[lat, lng] for lng, lat in coords],
            )
        )
    return routes


def _osrm_candidate_routes(
    origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float
) -> list[CandidateRoute]:
    settings = get_settings()
    url = (
        f"{settings.routing_service_url}/route/v1/foot/"
        f"{origin_lng},{origin_lat};{destination_lng},{destination_lat}"
    )
    params = {"alternatives": "true", "overview": "full", "geometries": "geojson"}
    response = httpx.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    routes: list[CandidateRoute] = []
    for i, route in enumerate(data.get("routes", [])):
        coords = route["geometry"]["coordinates"]  # [[lng, lat], ...]
        routes.append(
            CandidateRoute(
                route_id=f"osrm-{i}",
                label=f"Route {i + 1}",
                distance_km=round(route["distance"] / 1000, 2),
                duration_min=round(route["duration"] / 60, 1),
                geometry=[[lat, lng] for lng, lat in coords],
            )
        )
    return routes


def _mock_candidate_routes(
    origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float
) -> list[CandidateRoute]:
    """
    Deterministic fixture routes so the frontend/DS teams can build against
    a stable response before the real routing provider is confirmed. Mirrors
    the three-route example on the Prototype slide (Flinders Lane / Swanston
    Street / Little Bourke St).
    """
    mid_lat = (origin_lat + destination_lat) / 2
    mid_lng = (origin_lng + destination_lng) / 2
    return [
        CandidateRoute(
            route_id="mock-flinders-lane",
            label="Via Flinders Lane",
            distance_km=1.4,
            duration_min=18,
            geometry=[
                [origin_lat, origin_lng],
                [mid_lat, mid_lng],
                [destination_lat, destination_lng],
            ],
        ),
        CandidateRoute(
            route_id="mock-swanston-street",
            label="Via Swanston Street",
            distance_km=0.9,
            duration_min=12,
            geometry=[
                [origin_lat, origin_lng],
                [mid_lat + 0.0005, mid_lng],
                [destination_lat, destination_lng],
            ],
        ),
        CandidateRoute(
            route_id="mock-little-bourke-st",
            label="Via Little Bourke St",
            distance_km=1.6,
            duration_min=21,
            geometry=[
                [origin_lat, origin_lng],
                [mid_lat - 0.0005, mid_lng],
                [destination_lat, destination_lng],
            ],
        ),
    ]
