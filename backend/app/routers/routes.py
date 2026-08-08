"""
US 1.1 - Display Route Sensory Level (route comparison)
US 1.2 - Avoid Highly Congested Areas (congestion-aware route + text notification)

Both live on one endpoint: the frontend's "Plan" screen shows the same
route list either way, just annotated with LOW/HIGH/NO DATA and, for the
recommended route, a text notification when a corridor was avoided.
Per the prototype ("notifying the user by text, not voice") notifications
are plain text fields, not push/audio.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app import schemas
from app.services import sensory_scoring, routing_service
from app.services.sensory_scoring import SensorBaseline, SensorReading

router = APIRouter(prefix="/api/routes", tags=["routes"])


def _fixture_sensor_data_for(route_id: str):
    """
    Placeholder standing in for DS1/DS2/DS3's "match sensors to route by
    buffer radius" step until their tables (sensors, sensor_baseline,
    current_readings) are queryable from here. Swap this for a real query
    once DS3's matching function is available - the score_route() call
    below does not need to change.
    """
    fixtures = {
        "mock-flinders-lane": (["sensor-67"], {"sensor-67": SensorReading("sensor-67", 40)},
                                {"sensor-67": SensorBaseline("sensor-67", 60, 30)}),
        "mock-swanston-street": (["sensor-68"], {"sensor-68": SensorReading("sensor-68", 210)},
                                  {"sensor-68": SensorBaseline("sensor-68", 90, 30)}),
        "mock-little-bourke-st": ([], {}, {}),
    }
    return fixtures.get(route_id, ([], {}, {}))


@router.post("/compare", response_model=schemas.RouteCompareResponse)
def compare_routes(payload: schemas.RouteCompareRequest):
    candidates = routing_service.get_candidate_routes(
        payload.origin_lat, payload.origin_lng, payload.destination_lat, payload.destination_lng
    )

    options: list[schemas.RouteOption] = []
    for candidate in candidates:
        matched_ids, readings, baselines = _fixture_sensor_data_for(candidate.route_id)
        status, notification = sensory_scoring.score_route(matched_ids, readings, baselines)

        avoided_corridor = None
        if status == sensory_scoring.HIGH:
            avoided_corridor = candidate.label

        options.append(
            schemas.RouteOption(
                route_id=candidate.route_id,
                label=candidate.label,
                distance_km=candidate.distance_km,
                duration_min=candidate.duration_min,
                sensory_status=status,
                geometry=candidate.geometry,
                avoided_corridor=avoided_corridor,
                notification=notification,
            )
        )

    return schemas.RouteCompareResponse(routes=options, generated_at=datetime.now(timezone.utc))
