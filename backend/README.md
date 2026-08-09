# Backend API — Sensory-Friendly Urban Futures (IT scope)

FastAPI backend for the Week 3 onboarding iteration. Covers the two Must
Have epics from the deck:

- **US 1.1** Route sensory comparison — `POST /api/routes/compare`
- **US 1.2** Congestion avoidance — same endpoint, returns `avoided_corridor`
  + a text `notification` when a route is flagged HIGH
- **US 2.1** Sensory refuge locations — `GET /api/refuges`

No account/login system — every endpoint above is public/anonymous.
The team decided against user accounts for privacy reasons (per the
tutor's guidance), so there's no `/api/auth/*`, no per-user preferences,
and nothing in the API is scoped to a signed-in user. Plus a pluggable
routing-service client.

Database: the same shared **MySQL (AWS RDS)** instance the repo-root
`db.py` already uses — see "How this merges" below.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env already has the shared DB_HOST/DB_PORT/DB_USER/DB_NAME - ask the
# team for DB_PASSWORD (same one db.py's connect() asks for) and fill it in.
uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

## Before deploying (Render or anywhere else)

`.env.example` intentionally defaults to `ROUTING_PROVIDER=mock` so local
dev/tests work with zero setup - copying it as-is to a real deployment
will NOT activate real routing, it'll silently keep serving fixture
routes (the API still returns 200s, so this is easy to miss). Before
deploying, set these explicitly in the platform's environment variables
(not just in a local `.env` - a deployed instance never reads that file):

- `ROUTING_PROVIDER=openrouteservice`
- `ROUTING_SERVICE_API_KEY=<your key>`
- `DB_PASSWORD=<real password>`
- `FRONTEND_ORIGIN=<the deployed frontend's real URL>`

The app logs a warning at startup if `ROUTING_PROVIDER` is still `mock`
(see `app/main.py::lifespan`) - check the platform's startup logs after
deploying to confirm it didn't fire.

## Run tests

```bash
cd backend
pytest -v
```

Tests set `DATABASE_URL=sqlite:///:memory:` directly (see
`tests/conftest.py`), which overrides the MySQL settings above, and use
the `mock` routing provider — so they run without touching the shared
database or the network, same reasoning DS teams would use for their own
unit tests.

## How this merges into the existing repo

The repo already has `ds1-ingestion/`, `ds2-baseline/`, and a root
`db.py` that connects to the team's shared MySQL RDS instance via
`pymysql`. One thing to flag to DS1, not blocking review:

1. **Two connection styles, one database.** `db.py` opens raw
   `pymysql` connections (`db.connect()`) — right tool for DS1/DS2's
   ingestion/batch scripts. `app/database.py` here opens a SQLAlchemy
   ORM engine for the FastAPI layer. Both are configured from the same
   env vars (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`)
   and point at the same instance/database — they don't need to be
   unified into one client, just kept pointed at the same place, which
   they now are.
2. **Table ownership (confirmed against the live DB via `DESCRIBE`, not
   just the ERD deck).** `app/models.py` maps `route`, `location`,
   `support_location`, `environment`, `baseline`, `pedestrian_count_minute`
   — all already exist in the shared DB. There is no separate `sensors`
   table: a `location` row with `location_type='sensor'` IS a
   pedestrian-counting point, and `location_type='refuge'` rows are the
   sensory refuges (category one of Park / Library / Gallery or museum /
   Quiet place of worship). `route.preference_id` is `NOT NULL` in the
   real table even though this backend has no preferences/accounts
   concept anymore — nothing here writes to `route` currently, so it's
   not a blocking conflict, but flag it to whoever owns that table.
3. **`Base.metadata.create_all()`** in `app/main.py`'s startup is a no-op
   for every table above in the real DB (they already exist) — it only
   matters for the in-memory sqlite DB tests run against.
4. **No account system.** `app/routers/auth.py`, `app/routers/users.py`,
   and `app/core/security.py` are unused leftovers from an earlier drop —
   the team decided against user accounts for privacy reasons (per the
   tutor's guidance). Run `git rm backend/app/routers/auth.py
   backend/app/routers/users.py backend/app/core/security.py` to remove
   them; they're already unwired from `app/main.py` so leaving them in
   place is harmless but messy.
5. **DS3's scoring module (`ds3-sensory-scoring/`) is a sibling folder to
   `backend/`**, not part of it - `backend/app/services/sensory_scoring.py`
   is a copy of `ds3-sensory-scoring/sensory_scoring.py` (PR #4), kept in
   sync manually rather than imported across the two folders, since
   `backend/`'s FastAPI app and `ds3-sensory-scoring/`'s standalone
   script have different dependency/packaging needs. If DS3 updates their
   version, that copy needs updating here too - not automatic.

CI workflow and PR template already live at the repo root
(`.github/workflows/ci.yml`, `.github/PULL_REQUEST_TEMPLATE.md`) - not
duplicated under `backend/` in this drop.

## Real data status

- **Routing — done.** `ROUTING_PROVIDER=openrouteservice` calls the real
  OpenRouteService walking-directions API (free tier, no server to host).
  Get a free key at https://openrouteservice.org/dev/#/signup, put it in
  `ROUTING_SERVICE_API_KEY`, set `ROUTING_PROVIDER=openrouteservice` in
  `.env`. Note: it may return fewer than 3 alternative routes depending on
  the origin/destination (foot-walking alternatives are best-effort) — the
  `mock` provider is what still guarantees exactly 3, for demos.
- **Refuge locations — done.** `GET /api/refuges` queries real
  `location` rows (`location_type='refuge'`), with real lat/lng distance
  filtering. No fixture fallback.
- **Sensor data (route LOW/HIGH/NO DATA) — done, using DS3's approved
  implementation.** `app/services/sensory_scoring.py` is ported verbatim
  from DS3's `ds3-sensory-scoring/sensory_scoring.py` (PR #4), not a
  backend-written placeholder. `app/routers/routes.py` only does the
  SQLAlchemy glue (fetching sensor locations, the latest
  `pedestrian_count_minute` row per sensor, and the matching `baseline`
  row) and hands the data to DS3's unmodified `match_sensors_to_route()`
  and `score_route()`. This gets DS3's staleness check (readings older
  than `live_max_age_minutes`, default 30, are treated as NO DATA) and
  absolute HIGH threshold (not just relative-to-baseline, so a quiet
  corridor's baseline noise can't trigger a false HIGH).
- **`baseline.day_of_week` convention — verified, not assumed.**
  `melbourne_baseline_slot()` uses `datetime.weekday()` (Monday=0).
  Confirmed against real DS2 output, not just inferred from DS3's code:
  `SELECT sensing_date, day_of_week FROM pedestrian_count_hour LIMIT 10;`
  against the live shared DB returns `2025-08-11` (a real-world Monday)
  with `day_of_week=0` - see the
  `DayOfWeekProducerConventionTests` in `tests/test_sensory_scoring.py`,
  which encodes this exact fact as a regression test.
- **`ScoringConfig` now loads from the shared DB's `config` table.**
  `app/services/scoring_config.py::load_scoring_config()` is a SQLAlchemy
  port of DS3's `load_config()` (same keys, same fallback defaults,
  wired into `compare_routes()`). As of 2026-08-09 only
  `absolute_threshold` (500), `minimum_observations` (10), and
  `relative_threshold` (1.5) are actually populated in `config` -
  `route_buffer_radius_m`, `minimum_route_sensors`, and
  `live_max_age_minutes` fall back to `ScoringConfig`'s own defaults
  until DS2 adds rows for them. `tests/test_scoring_config.py` covers
  both the populated-key and fallback-default paths, plus a regression
  test proving a DB-level override actually changes a route's scored
  outcome (not just that the config value gets parsed).
- **Deployment platform + scheduled jobs** (daily batch, 15-min poll) are
  out of scope for this drop — this README/API is the piece to plug into
  whatever platform gets chosen next.

## Security notes (matches the Security Plan slide)

- No account/login system — the product collects no usernames or
  passwords, per the tutor's privacy guidance, so there's nothing to hash
  or leak on that front.
- `.env` is gitignored; only `.env.example` (no real secrets, `DB_PASSWORD`
  left blank) is committed — matches db.py's "ask the team for it" model.
- `score_route()` returns `NO DATA` instead of guessing whenever matching
  sensors, baseline observations, or live readings are missing — a wrong
  LOW is a safety issue, not just an accuracy issue.
