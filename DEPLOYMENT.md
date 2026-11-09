# Deploying Octopod on Cloudflare

Octopod deploys as **one Cloudflare Worker**:

- **Static Assets** serves the React build from `frontend/dist` for free.
- **`workers.asgi`** runs the FastAPI application for every `/api/*` request.
- **D1** is the production database.
- **Durable Objects** provide Argon2 hashing (`CryptoBox`) and rate limiting
  (`RateLimiter`). `Generator` and `Renderer` are optional offloads: the
  default roster-generation path runs in the Worker, and PNG export renders in
  the browser.

The SPA and API share one origin, so there is no CORS proxy, no separate
frontend project, and no separate backend host.

> **Current deployment:** <https://octopod.aftabsd786.workers.dev>, backed by the
> D1 database `octopod`. Treat hostnames, account IDs, and database IDs in this
> guide as environment-specific values when recreating the stack elsewhere.

> The files that matter are `backend/wrangler.jsonc`, `backend/src/worker.py`,
> `backend/migrations/d1/`, and `backend/src/app/workers/`. Build the frontend
> before deploying because Static Assets uploads `frontend/dist`.

---

## 1. Prerequisites

- A Cloudflare account (the free plan is enough for a small team).
- Node.js 20+ (for `wrangler` and the frontend build).
- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) 0.13.4 or newer
  (`pywrangler` refuses older versions).
- `wrangler` authentication: `npx wrangler login`.

Install dependencies:

```bash
cd backend && uv sync
cd ../frontend && npm install
```

`pywrangler` (provided by `workers-py`) wraps Wrangler and knows how to bundle
the Python Worker. All commands below are run from `backend/` unless noted.

---

## 2. One-time Cloudflare setup

### 2.1 Create the D1 database

```bash
npx wrangler d1 create octopod
```

Copy the returned `database_id` into `backend/wrangler.jsonc`. The committed
file already points at the `octopod` database used by the current deployment;
D1 database IDs are identifiers, not secrets:

```jsonc
"d1_databases": [
  {
    "binding": "DB",
    "database_name": "octopod",
    "database_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "migrations_dir": "migrations/d1"
  }
]
```

### 2.2 Set the secret

`SECRET_KEY` must never live in the repository or `wrangler.jsonc`:

```bash
npx wrangler secret put SECRET_KEY
```

Generate a strong value locally, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2.3 Review public vars

Non-secret configuration is in the `vars` block:

```jsonc
"vars": {
  "ENVIRONMENT": "production",
  "COOKIE_SECURE": "true",
  "AUTO_CREATE_TABLES": "false",
  "SEED_DEMO": "false",
  "ALLOWED_ORIGINS": "https://roster.example.com"
}
```

Set `ALLOWED_ORIGINS` to the Worker's production hostname (or your custom
domain). Because the SPA and API are same-origin, CORS is only needed for
explicit cross-origin clients such as the Vite development server during
development.

### 2.4 Durable Object migrations

The `migrations` block in `wrangler.jsonc` declares the SQLite-backed Durable
Object classes. `CryptoBox`, `RateLimiter`, `Generator`, and `Renderer` are
created on the first deploy; subsequent class additions require a new tagged
migration entry.

---

## 3. Local development

### 3.1 Worker + local D1 (recommended)

Build the SPA once, then apply migrations and start the Worker:

```bash
cd frontend && npm run build
cd ../backend

npx wrangler d1 migrations apply octopod --local
uv run pywrangler dev --port 8787
```

Open <http://localhost:8787>. Miniflare creates a local D1 database and exposes
it through the `DB` binding, so the Worker code path is the same as production.

`pywrangler dev` reads `backend/.dev.vars` for local secrets and vars. Copy
`.dev.vars.example` to `.dev.vars`. A minimal file:

```dotenv
ENVIRONMENT=development
SECRET_KEY=dev-secret-change-me
COOKIE_SECURE=false
SEED_DEMO=false
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Never commit `.dev.vars` (it is ignored).

### 3.2 Frontend hot reload

Run Vite separately for fast UI iteration:

```bash
cd frontend
npm run dev
```

Vite serves the SPA on <http://localhost:5173> and proxies `/api` to the Worker
on `http://localhost:8787` (configured in `frontend/vite.config.ts`).

### 3.3 Local API server for tests and scripts

The pytest and Playwright suites use the traditional SQLAlchemy path instead of
the Worker runtime:

```bash
cd backend
DATABASE_URL=sqlite:///./octopod.db \
AUTO_CREATE_TABLES=true SEED_DEMO=false SECRET_KEY=test-secret \
uv run uvicorn app.main:app --app-dir src --reload --port 8000
```

This path does not serve the built SPA. Use it for tests, scripts, or debugging
service code without the Worker runtime. Set `SEED_DEMO=true` if you want the
demo dataset. The D1 maintenance scripts are separate:
`scripts/create_admin.py` writes through `wrangler d1 execute`, and
`scripts/check_d1_schema.py` applies the SQL migrations to an in-memory SQLite
database to compare them with the SQLAlchemy metadata.

### 3.4 Create a local administrator

```bash
uv run python scripts/create_admin.py --local --email admin@example.com
```

The script prompts for a password, hashes it with the application's Argon2
parameters, and inserts the user through `wrangler d1 execute --local`.

---

## 4. Deploy

### 4.1 Build the SPA

```bash
cd frontend
npm run build
```

The output is `frontend/dist/`. Static Assets uploads it as part of the Worker
deployment.

### 4.2 Apply D1 migrations

```bash
cd backend
npx wrangler d1 migrations apply octopod --remote
```

Migrations live in `backend/migrations/d1/` and are applied in filename order.
D1 tracks applied migrations, so this command is safe to run on every deploy.
D1 enforces stricter SQL limits than local SQLite (for example, a bounded number
of terms in a compound `SELECT`), so keep large data migrations to recursive
CTEs or several statements and test them against a staging D1 database.

### 4.3 Deploy the Worker

```bash
uv run pywrangler deploy
```

Wrangler bundles the Python Worker, uploads assets, and applies the Durable
Object migration. The first deploy creates the Worker and its bindings.

### 4.4 Create the first production administrator

```bash
uv run python scripts/create_admin.py --remote --email you@company.com
```

There is no public admin-registration endpoint.

### 4.5 Verify

```bash
curl -fsS https://<worker-host>/api/v1/health
curl -fsSI https://<worker-host>/ | head -n 1
npx wrangler d1 execute octopod --remote \
  --command "SELECT count(*) AS users FROM users;"
```

Then sign in at `https://<worker-host>/login`, open a roster, and download a
PNG to confirm client-side export works.

---

## 5. Custom domain

In the Cloudflare dashboard, open **Workers & Pages → octopod → Settings →
Domains & Routes** and add your hostname. Update `ALLOWED_ORIGINS` to match, then
redeploy:

```bash
uv run pywrangler deploy
```

Cloudflare terminates TLS automatically; keep `COOKIE_SECURE=true`.

---

## 6. Data import and export

D1 keeps the production data. To move data between environments, export a SQL
dump from the source database and apply it to the target after the schema
migrations have run:

```bash
npx wrangler d1 export octopod --remote --output octopod-$(date +%F).sql
npx wrangler d1 execute octopod --remote --file=./octopod-2026-11-09.sql
npx wrangler d1 execute octopod --remote --command "PRAGMA foreign_key_check;"
npx wrangler d1 execute octopod --remote --command "PRAGMA integrity_check;"
```

Always import into a staging D1 database first and verify row counts and a few
password logins. Argon2 hashes are preserved verbatim, so users keep their
existing passwords.

---

## 7. Day-2 operations

### Logs

```bash
npx wrangler tail octopod --format pretty
```

`wrangler tail` includes CPU time and exceptions. Watch the `X-Query-Count`
response header and server logs when optimising D1 round trips.

### Deploy a new version

```bash
cd frontend && npm run build
cd ../backend
npx wrangler d1 migrations apply octopod --remote
uv run pywrangler deploy
```

Assets and API ship together, so there is no frontend/backend version skew.

### Roll back

```bash
npx wrangler deployments list
npx wrangler rollback <DEPLOYMENT_ID>
```

A Worker rollback does not roll back D1 schema changes. Write migrations to be
backward-compatible for at least one deploy, or restore D1 with Time Travel
before rolling back code.

### Backups

```bash
npx wrangler d1 export octopod --remote --output octopod-$(date +%F).sql
```

Keep exports outside Cloudflare. D1 Time Travel can restore a database to a
point in the last 30 days:

```bash
npx wrangler d1 time-travel restore octopod --timestamp <ISO_TIMESTAMP>
```

### Pruning old sessions

Expired sessions are ignored by the application. If the `user_sessions` table
grows large, prune it periodically:

```bash
npx wrangler d1 execute octopod --remote \
  --command "DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP;"
```

---

## 8. Free-tier limits and capacity

| Resource | Free allowance | Notes |
|----------|----------------|-------|
| Worker requests | 100,000/day | `/api/*` counts; static assets do not. |
| Worker CPU | 10 ms/invocation (paid: configurable) | Argon2 is offloaded to a Durable Object; generation is small enough to run in the Worker. |
| D1 storage | 5 GB | Total database size. |
| D1 rows read | 5M/day | Batch reads where possible and avoid N+1 queries. |
| D1 rows written | 100k/day | `batch()` groups related writes; each row still counts. |
| Durable Objects | SQLite-backed classes | Used for crypto and rate limiting; generation/rendering classes are optional. |

A small team (tens of users, a few hundred requests per user per day) fits
comfortably. If the Worker request limit is exhausted, API requests fail closed
while Static Assets continues to serve the SPA.

---

## 9. CI/CD

`.github/workflows/ci.yml` runs backend lint/tests, a D1 schema parity check, a
Worker dry-run, frontend type/tests/build, and a deploy job on `main`.

Required repository secrets:

- `CLOUDFLARE_API_TOKEN` — an API token with Workers Scripts:Edit, D1:Edit, and
  (if using a custom domain) Workers Routes:Edit.
- `CLOUDFLARE_ACCOUNT_ID` — the account ID shown in the dashboard.

The D1 database ID is committed in `backend/wrangler.jsonc`, so it does not need
to be a repository secret. The deploy job builds the SPA, applies remote D1
migrations, and runs `pywrangler deploy`. If you prefer manual releases, disable
the `deploy` job and run the commands in section 7 yourself.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `DB is not defined` / D1 errors | Binding missing or wrong id | Check `d1_databases` in `wrangler.jsonc` and redeploy. |
| Login works locally but not in production | `SECRET_KEY` missing or changed | `npx wrangler secret put SECRET_KEY`, then redeploy. |
| Cookie rejected over HTTPS | `COOKIE_SECURE=false` | Set `COOKIE_SECURE=true` in vars. |
| CORS errors from a separate origin | Origin missing from `ALLOWED_ORIGINS` | Add it to the comma-separated list. |
| SPA routes return API 404 | Static Assets not built/uploaded | Run `npm run build` before deploying. |
| `no such table` | D1 migrations not applied | `npx wrangler d1 migrations apply octopod --remote`. |
| Migration fails with a SQL limit error | Large compound `SELECT` or too many terms | Use a recursive CTE or split the statement; test against remote D1. |
| Batch write fails or proxies are destroyed | Prepared statements converted with `to_js()` | Call `d1_batch()` with the prepared statements list; do not wrap it. |
| Worker CPU exceeded | Large roster generation or rendering | Generation can be moved to the `Generator` DO; PNG export is already client-side. |
| PNG export fails | Canvas blocked or no roster data | Check the browser console; the client renders the loaded grid. |
| Old JS after deploy | Service worker cache | Reload twice or unregister the service worker in dev tools. |

### Useful commands

```bash
npx wrangler deployments list
npx wrangler tail octopod
npx wrangler d1 migrations list octopod --local
npx wrangler d1 migrations list octopod --remote
npx wrangler d1 execute octopod --local --command "SELECT name FROM sqlite_master;"
uv run python scripts/check_d1_schema.py
```

---

## References

- [Cloudflare Workers Python](https://developers.cloudflare.com/workers/languages/python/)
- [Static Assets](https://developers.cloudflare.com/workers/static-assets/)
- [D1 migrations](https://developers.cloudflare.com/d1/reference/migrations/)
- [Durable Objects](https://developers.cloudflare.com/durable-objects/)
- [Wrangler commands](https://developers.cloudflare.com/workers/wrangler/commands/)
