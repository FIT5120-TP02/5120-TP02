"""
FastAPI app entrypoint - "Integration and release" (IT's responsibility).

Run locally:
    uvicorn app.main:app --reload

Docs once running: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database import Base, engine
from app.routers import auth, refuges, routes, users

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience only. In staging/prod, use real migrations (Alembic)
    # instead of create_all, and coordinate with DS1's db.py so both sides
    # aren't racing to define the same tables.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Sensory-Friendly Urban Futures API",
    description="Backend for sensory-aware route planning in Melbourne CBD (UNSDG 11).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(routes.router)
app.include_router(refuges.router)


@app.get("/health")
def health():
    return {"status": "ok"}
