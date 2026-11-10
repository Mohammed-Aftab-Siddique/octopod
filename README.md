# Octopod Roster

A simple, responsive roster management PWA. Administrators manage employees,
availability, staffing requirements, and monthly rosters; employees sign in to
view the published roster (their own row by default, with a full-team view).

Built with React + TypeScript + Vite + Tailwind on the frontend, and FastAPI +
SQLAlchemy on the backend. Production runs as a single Cloudflare Worker:
Static Assets serves the React build, `workers.asgi` runs FastAPI under
`/api/*`, D1 (SQLite) stores data, and Durable Objects handle Argon2 and
rate limiting, with optional roster-generation and server-render offloads. See
[`GOAL.md`](./GOAL.md) / [`TECH_STACK.md`](./TECH_STACK.md) for requirements and
architecture, [`BEST_PRACTICES.md`](./BEST_PRACTICES.md) for engineering
standards, [`SOP.md`](./SOP.md) for the user guide, and
[`DEPLOYMENT.md`](./DEPLOYMENT.md) for the Cloudflare deployment guide.

## Features

- Admin and employee roles with server-enforced permissions and CSRF protection.
- Employee CRUD, deactivation, unique employee IDs, and public name lookup.
- Approved leave, comp-off, week-off, and unavailable dates (date ranges).
- Monthly roster drafts rendered as an employee × date grid with sticky headers.
- Seven statuses plus a holiday `H` code, all colour-coded with a legend.
- Assisted generation with a fixed primary shift per employee, rotating
  week-offs, staffing requirements, leave exclusion, and shortage reporting.
- Explicit publish approval, immutable published versions, and archived history.
- Employee self-view (own row by default) and full-team read-only view.
- PNG export rendered client-side (month, dates, names, statuses, and legend).
- PWA manifest and service worker (installable; offline editing is out of scope).
- Per-employee primary shift and weekly days off; holidays configured per month.

## Quick start (Linux / macOS)

Prerequisites: Node.js 20+, Python 3.12+, and `uv` 0.13.4+. Wrangler downloads
automatically through the `pywrangler` tool; no external database server is
needed.

```bash
# 1. Install dependencies
cd backend && uv sync
cd ../frontend && npm install

# 2. Build the SPA once so the Worker has assets to serve
npm run build
cd ../backend

# 3. Apply the D1 schema locally
npx wrangler d1 migrations apply octopod --local

# 4. Create a local administrator (there is no public signup endpoint)
uv run python scripts/create_admin.py --local --email admin@example.com

# 5. Start the Worker (FastAPI + Static Assets)
uv run pywrangler dev --port 8787
```

Open http://localhost:8787. During UI development you can instead run
`npm run dev` in `frontend/`; Vite serves the SPA on port 5173 and proxies
`/api` to the Worker on port 8787.

> The demo seed is opt-in. `pywrangler dev` reads `backend/.dev.vars`; copy
> `backend/.dev.vars.example` to get started. See
> [`DEPLOYMENT.md`](./DEPLOYMENT.md) for details.

### Demo accounts

These accounts exist only when the database is seeded with `SEED_DEMO=true`,
which is useful for local demos and the Playwright suite. A production D1
deployment uses the administrator you create with `scripts/create_admin.py`.

| Role | Identifier | Password |
|------|------------|----------|
| Administrator | `admin@example.com` | `Admin123!` |
| Employee | `EMP001` or `atharv@example.com` | `Employee123!` |

New employees created through the UI also use `Employee123!` if no initial
password is supplied.

## Production-style run (single Worker)

```bash
cd frontend && npm run build
cd ../backend
npx wrangler d1 migrations apply octopod --remote
uv run pywrangler deploy
```

The Worker serves the SPA and the API from one origin, so the API is available
at `/api/v1` and interactive docs at `/api/docs`. See
[`DEPLOYMENT.md`](./DEPLOYMENT.md) for D1 creation, secrets, Durable Object
migrations, and rollback.

## Local database options

- **Worker + D1 (default):** `npx wrangler d1 migrations apply octopod --local`
  against Miniflare's local D1 database. This matches production.
- **Temporary SQLite (pytest and Playwright):** the test suites create an
  isolated SQLite database and exercise the FastAPI app in-process (pytest) or
  through Uvicorn (Playwright). Tests never touch a development database.
- **D1 integration:** tests marked `d1` require `pywrangler dev` and a local D1
  database.

## Environment

For the Worker, non-secret values live in the `vars` block of
`backend/wrangler.jsonc`, and secrets are set with
`npx wrangler secret put SECRET_KEY`. Local Worker development reads
`backend/.dev.vars` (copy `backend/.dev.vars.example`). The pytest and Playwright
suites set their own environment variables, including a temporary
`DATABASE_URL`.

| Variable | Default | Notes |
|----------|---------|-------|
| `ENVIRONMENT` | `development` | Set `production` for deployed instances. |
| `SECRET_KEY` | dev value | Long random value; Worker secret in production. |
| `SESSION_COOKIE_NAME` | `octopod_session` | HttpOnly session cookie. |
| `SESSION_TTL_HOURS` | `168` | Session lifetime. |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS. |
| `AUTO_CREATE_TABLES` | `false` | Test/local convenience; keep `false` on Workers. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed by CORS. |
| `SEED_DEMO` | `false` | Seed demo data when no admin exists. Never enable in production. |
| `VITE_API_BASE_URL` | `/api/v1` | Frontend API base URL. |

The Worker obtains its database from the `DB` D1 binding; `DATABASE_URL` is used
only by the test suites and the optional local API server.

## Project structure

```text
backend/
  src/
    app/
      api/v1/        # auth, employees, reference data, rosters, health
      core/          # settings, password hashing, rate limiting
      db/            # engine/session and D1 batch helpers
      models/        # SQLAlchemy models
      schemas/       # Pydantic request/response models
      services/      # employee, roster, generation, export, seed logic
      workers/       # Durable Objects: crypto, rate limiting, generator, renderer
    worker.py        # Worker entrypoint (Default = asgi.entrypoint)
  migrations/
    d1/            # D1 SQL migrations (production schema)
  scripts/         # create admin and D1 schema check
  tests/           # pytest suite
  wrangler.jsonc   # Worker, Static Assets, D1, and Durable Object config
docs/
  decisions.md     # product and engineering decisions
frontend/
  src/
    api/           # typed fetch client
    components/    # UI primitives, layout, roster grid/legend/picker
    features/      # auth, employees, roster, settings pages
    lib/           # types, utilities, and client-side PNG export
  e2e/             # Playwright tests
  public/          # PWA icons
DEPLOYMENT.md      # Cloudflare deployment guide
GOAL.md            # product requirements
SOP.md             # end-user and administrator procedures
TECH_STACK.md      # technology and architecture
BEST_PRACTICES.md  # engineering standards
```

## Roster generation

Generation is deterministic backend logic (no external optimiser):

1. Active employees are filtered against approved leave, comp-off, week-off,
   and unavailable dates.
2. Holidays receive the `H` status for everyone.
3. Each employee keeps a fixed primary shift for the month (`default_shift`,
   or a balanced shift derived from `rotation_offset`). Days off rotate
   independently: `weekly_off_days` consecutive days per week, staggered by
   `rotation_offset`.
4. Staffing requirements for the weekday drive coverage. The generator can pull
   employees out of a planned day off (or add a day off), and move employees to
   another shift only when the fixed-shift mix cannot cover it, while tracking
   fairness counters.
5. Shortages are returned for administrator review. Generated rosters are
   always drafts and require explicit publish approval.

Generation never auto-publishes. Publishing archives the previously published
version for the month and makes the new version visible to employees.

## API overview

All endpoints are under `/api/v1`.

- `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET /employees/lookup?employee_code=...`
- `GET|POST /employees`, `GET|PATCH /employees/{id}`,
  `POST /employees/{id}/deactivate`, `POST /employees/{id}/reset-password`
- `GET|POST /employees/{id}/availability`,
  `DELETE /employees/{id}/availability/{availability_id}`
- `GET /reference/shift-statuses`
- `GET|PUT /reference/staffing-requirements`
- `GET|POST /reference/holidays`, `DELETE /reference/holidays/{id}`
- `GET|POST /rosters`, `GET /rosters/{id}`,
  `PATCH /rosters/{id}/assignments`, `POST /rosters/{id}/generate`,
  `POST /rosters/{id}/publish`, `GET /rosters/{id}/export.png`
- `GET /me/roster?year=&month=`
- `GET /health`

Authentication uses an HttpOnly session cookie and an `X-CSRF-Token` header for
mutations. Roles are enforced on every protected backend operation. Employee ID
lookup returns only the employee code and name and never grants access.

## Testing

```bash
# Backend static checks, unit/API tests, and D1 schema parity
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python scripts/check_d1_schema.py

# Frontend type checks, unit tests and production build
cd frontend
npm run typecheck
npm test
npm run build

# End-to-end tests (desktop + mobile viewports)
cd frontend
npx playwright install chromium   # once
npx playwright test
```

The Playwright configuration starts an isolated FastAPI test server on port
`8787` with a fresh SQLite database in the system temp directory, while Vite
serves the SPA on port `8010` and proxies `/api` to it. This keeps E2E fast and
independent of the Worker runtime while exercising the real frontend. It removes
any previous E2E database, seeds demo data for the current month, and never
reuses a running developer server or touches a local D1 database. Set
`E2E_BASE_URL` to test an already-running deployment instead.

For a local Worker smoke test, run `npm run build`, apply D1 migrations with
`npx wrangler d1 migrations apply octopod --local`, and start
`uv run pywrangler dev`.

## Deployment notes

- The current production deployment is
  <https://octopod.aftabsd786.workers.dev> (D1 database `octopod`). Command
  examples below use placeholders so the guide applies to other environments.
- Deploy one Worker with `uv run pywrangler deploy` after `npm run build`;
  Static Assets serves `frontend/dist` and `/api/*` invokes FastAPI.
- Apply D1 migrations with `npx wrangler d1 migrations apply octopod --remote`.
- Set `SECRET_KEY` with `npx wrangler secret put SECRET_KEY`; keep
  `ENVIRONMENT=production`, `COOKIE_SECURE=true`, and `ALLOWED_ORIGINS` in
  `wrangler.jsonc` vars.
- Export D1 regularly (`npx wrangler d1 export octopod --remote --output ...`).
- `/health` is a liveness check only; it does not query the database.
- No Kubernetes, microservices, or message brokers are required. See
  [`DEPLOYMENT.md`](./DEPLOYMENT.md) for the full guide.
