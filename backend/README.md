# Backend API — Sensory-Friendly Urban Futures (IT scope)

FastAPI backend for the Week 3 onboarding iteration. Covers the two Must
Have epics from the deck:

- **US 1.1** Route sensory comparison — `POST /api/routes/compare`
- **US 1.2** Congestion avoidance — same endpoint, returns `avoided_corridor`
  + a text `notification` when a route is flagged HIGH
- **US 2.1** Sensory refuge locations — `GET /api/refuges`

Plus the supporting infrastructure: auth (`/api/auth/register`,
`/api/auth/login`), user preferences (`/api/users/me/preferences`), and a
pluggable routing-service client.

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
2. **Table ownership.** This backend defines `users`, `preferences`,
   `route`, `location`, `support_location`, `environment` per the ERD.
   DS1/DS2/DS3 own `sensors`, `hourly_counts`, `sensor_baseline`,
   `current_readings`, `refuge_locations` per the System Architecture
   slide. `app/services/sensory_scoring.py` and
   `app/routers/routes.py::_fixture_sensor_data_for` are placeholders that
   return mock sensor data — swap them for real queries once those tables
   exist, without changing the function signatures the routers call.
3. **`Base.metadata.create_all()`** in `app/main.py`'s startup will create
   this backend's tables (users/preferences/route/location/
   support_location/environment) in the shared database if they don't
   exist yet. If DS1 already created any of these via their own
   migration/script, delete the duplicate definition from `app/models.py`
   instead of letting both sides try to own the same table.

CI workflow and PR template already live at the repo root
(`.github/workflows/ci.yml`, `.github/PULL_REQUEST_TEMPLATE.md`) - not
duplicated under `backend/` in this drop.

## Open items / things to confirm with the team

- **Routing provider** — `ROUTING_PROVIDER=mock` by default so the API is
  usable immediately. `osrm` is implemented; free-tier hosted options
  (OpenRouteService, GraphHopper) still need a provider branch added to
  `app/services/routing_service.py` once the team picks one — factor in
  their daily request caps when deciding.
- **`location` table has no lat/lng columns** in the current ERD, but
  US 2.1 ("nearby" refuge search) needs coordinates. `refuges.py` falls
  back to a fixture list until this is added — flag to whoever owns the
  ERD/migrations.
- **`CROWD_HIGH_THRESHOLD_MULTIPLIER`** is a placeholder (1.5x baseline
  median). Per the deck, DS2 determines this empirically — update the env
  var once they have a number.
- **Deployment platform + scheduled jobs** (daily batch, 15-min poll) are
  out of scope for this drop — this README/API is the piece to plug into
  whatever platform gets chosen next.

## Security notes (matches the Security Plan slide)

- Passwords hashed with bcrypt, never stored/logged in plaintext.
- JWT-based auth; `get_current_user` scopes every user-data endpoint to
  the token owner — no user ID is ever accepted from the request body/URL
  for "my own data" endpoints.
- `.env` is gitignored; only `.env.example` (no real secrets, `DB_PASSWORD`
  left blank) is committed — matches db.py's "ask the team for it" model.
- `score_route()` returns `NO DATA` instead of guessing whenever matching
  sensors, baseline observations, or live readings are missing — a wrong
  LOW is a safety issue, not just an accuracy issue.
