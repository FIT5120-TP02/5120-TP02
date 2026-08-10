"""
FastAPI app entrypoint - "Integration and release" (IT's responsibility).

Run locally:
    uvicorn app.main:app --reload

Docs once running: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database import Base, engine
from app.routers import refuges, routes

settings = get_settings()
logger = logging.getLogger("app.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience only. In staging/prod, use real migrations (Alembic)
    # instead of create_all, and coordinate with DS1's db.py so both sides
    # aren't racing to define the same tables.
    Base.metadata.create_all(bind=engine)

    # `mock` is the correct default for local dev/tests, but a real
    # deployment silently left on `mock` would serve fixture routes
    # without anyone noticing (the API still returns 200s). Copying
    # .env.example alone does NOT switch this - it must be set explicitly
    # in the deployment platform's env vars. Log loudly so it shows up in
    # the platform's startup logs (e.g. Render) if this was forgotten.
    if settings.routing_provider == "mock":
        logger.warning(
            "ROUTING_PROVIDER=mock at startup - serving fixture routes, not "
            "real routing. If this is a real deployment (not local dev or "
            "tests), set ROUTING_PROVIDER=openrouteservice and "
            "ROUTING_SERVICE_API_KEY in the platform's environment variables."
        )
    yield


app = FastAPI(
    title="Sensory-Friendly Urban Futures API",
    description="Backend for sensory-aware route planning in Melbourne CBD (UNSDG 11).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # FRONTEND_ORIGIN accepts a comma-separated list (e.g. the deployed
    # frontend + a teammate's local dev server) so more than one origin
    # can be allowed without adding more env vars - see
    # Settings.frontend_origins in app/core/config.py.
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(refuges.router)


@app.get("/health")
def health():
    return {"status": "ok"}
