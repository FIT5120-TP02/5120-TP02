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
- **Sensor data (route LOW/HIGH/NO DATA) — done, one assumption to
  verify.** `app/routers/routes.py` matches `location_type='sensor'` rows
  to a candidate route by proximity (`SENSOR_MATCH_RADIUS_KM`, default
  100m) to any point on its polyline, pulls the latest
  `pedestrian_count_minute` row as the live reading, and the matching
  `baseline` row (by `day_of_week`/`hourday` for the current local time)
  as the baseline. **Unverified:** `baseline.day_of_week` is confirmed to
  range 0-6, but not confirmed whether 0 = Monday or Sunday — this code
  assumes Python's `datetime.weekday()` convention (Monday=0). If a route
  scores LOW/HIGH at an obviously wrong time of day, this is the first
  thing to check (see the comment in
  `app/routers/routes.py::_real_sensor_data_for`).
- **`CROWD_HIGH_THRESHOLD_MULTIPLIER`** is a placeholder (1.5x baseline
  median). Per the deck, DS2 determines this empirically — update the env
  var once they have a number.
- **`SENSOR_MATCH_RADIUS_KM`** (default 0.1km/100m) hasn't been tested
  against real route density in the CBD — tune if too many/few sensors
  match per route.
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
