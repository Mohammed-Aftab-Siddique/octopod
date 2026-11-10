# BEST_PRACTICES.md

Engineering and product practices for the Octopod roster application. This
document complements [`TECH_STACK.md`](./TECH_STACK.md), which defines *what*
we build with, and [`GOAL.md`](./GOAL.md), which defines *what* we build. This
file defines *how* we build it: conventions, quality gates, and MVP guardrails.

The practices below describe the stack as it is used in this repository today:
React 18 + TypeScript + Vite 5 + Tailwind 3 + shadcn/ui on the frontend, and
Python 3.12+ + FastAPI + Pydantic + SQLAlchemy 2 inside a single Cloudflare
Worker on the backend, with D1 as the production database and Durable Objects
for Argon2 hashing and rate limiting.

The rules are intentionally practical. Apply judgement, but if a change
contradicts this document, either update the document with a reason or adjust
the change.

---

## 1. Cross-cutting principles

- **Prefer simple, proven solutions.** Add a dependency, service, abstraction,
  or infrastructure component only when the current problem clearly requires
  it.
- **Keep the MVP small.** Ship the smallest coherent feature that satisfies a
  real user need, then iterate. Do not build for hypothetical scale.
- **Security and data integrity are not optional.** Authorization, validation,
  and database constraints belong in the backend even if the UI also checks
  them.
- **One source of truth per concern.** Backend owns business rules and roster
  generation; frontend owns presentation and interaction; the database owns
  referential integrity.
- **Match existing patterns before inventing new ones.** Look at neighbouring
  code first. Consistency is cheaper to maintain than local cleverness.
- **No silent failures.** Report errors to the user, log useful server-side
  context, and return explicit shortages/warnings rather than producing invalid
  data.
- **Leave the codebase easier to change.** Small functions, clear names,
  focused modules, and tests around the risky parts.
- **Do not commit secrets or generated artefacts.** `.env`, local databases,
  build output, caches, and credentials stay out of Git.

---

## 2. Frontend practices

### 2.1 Structure and conventions

- Use the `@/` path alias for imports from `frontend/src`.
- Organise by responsibility:
  - `src/api/` — typed HTTP client and request concerns.
  - `src/components/ui/` — reusable shadcn-style primitives.
  - `src/components/roster/` — roster-specific presentational components.
  - `src/features/` — page-level feature modules (auth, employees, roster,
    settings).
  - `src/lib/` — shared types, formatting, constants, and small utilities.
- Keep page components focused on composition and data flow. Extract reusable
  rendering and interaction into components.
- Do not create a new abstraction for a single use. Extract only when a pattern
  is repeated or the component is independently testable.
- Use function components and hooks. Avoid class components.
- Prefer named exports for components and utilities, matching the existing
  code.
- Keep files reasonably small. If a page exceeds roughly 300–400 lines or mixes
  several independent concerns, split it.

### 2.2 TypeScript

- `strict` is enabled. Do not weaken it and do not use `any` to silence errors.
  Prefer `unknown` plus narrowing where a type is genuinely unknown.
- Define shared API/domain shapes in `src/lib/types.ts`; do not duplicate them
  ad hoc across components.
- Use `import type` for type-only imports.
- Model UI states explicitly (`loading`, `error`, empty, success) rather than
  relying on odd combinations of booleans.
- Treat API data as untrusted at the boundary. Keep a consistent shape and map
  it deliberately when needed.
- Avoid non-null assertions (`!`) unless the invariant is obvious and local.
- Keep `tsc --noEmit` clean. The production build runs the type check first.

### 2.3 API communication

- All backend calls go through `src/api/client.ts`. Do not call `fetch`
  directly from components unless there is a specific, documented reason.
- Use the exported `api` helpers and `ApiError` so errors, CSRF headers, cookies,
  and JSON/blob handling stay consistent.
- Keep the API base URL configurable through `VITE_API_BASE_URL`; default to
  `/api/v1`.
- Use `credentials: "include"` semantics through the shared client. Never
  hand-roll a second auth mechanism.
- Pass the CSRF token through the existing client mechanism for mutations.
- For downloads, use `api.download()` so content type, errors, and filename
  handling remain consistent.

### 2.4 Server state and forms

- Use TanStack Query for all server-owned data. Components should render from
  query data, not duplicate it into local state.
- Choose stable, predictable query keys, for example `["roster", rosterId]`.
  Invalidate or update all affected keys after mutations.
- Use optimistic updates only where the UX benefit is clear (for example,
  single roster-cell edits). Always keep a previous snapshot and roll back on
  error.
- Do not add a global state library for data that belongs to the server.
- Use local component state for purely presentational concerns.
- Use React Hook Form with Zod for non-trivial forms. Share validation rules
  where practical, but remember backend validation is authoritative.
- Disable submit actions while mutations are in flight and surface field-level
  or form-level errors clearly.

### 2.5 Styling and UI

- Use Tailwind utility classes and the `cn()` helper (`clsx` +
  `tailwind-merge`) for conditional and merged classes.
- Use the existing shadcn-style primitives in `components/ui/` rather than
  recreating buttons, dialogs, inputs, and labels.
- Keep colours, spacing, and typography consistent with the existing design.
- Status colours and labels must come from backend reference data, not be
  hard-coded per component.
- Do not rely on colour alone to communicate status. Always show the status
  code or label, and keep contrast at WCAG AA or better.
- Ensure layouts work at mobile, tablet, and desktop widths. Roster surfaces
  must remain usable with horizontal scrolling and sticky headers.
- Prefer responsive, fluid layouts over fixed pixel dimensions except where a
  fixed size is required for export or a controlled grid.

### 2.6 Accessibility

- Use semantic HTML first: real `button`, `table`, `th`, `td`, `label`, and
  `nav` elements.
- Every interactive control needs an accessible name. Roster cells should
  announce employee, date, and status, not just a code.
- Support keyboard navigation for editing surfaces. Never make a `div`
  clickable when a `button` is appropriate.
- When using dialogs or popovers, manage focus and escape behaviour through the
  existing primitives.
- Test critical screens with keyboard-only navigation and a screen reader or
  accessibility inspector before considering a UI milestone done.
- Provide visible focus states and do not suppress outlines without a
  replacement.

### 2.7 Dates

- Send and receive roster dates as ISO `YYYY-MM-DD` strings.
- Derive day-of-week and month boundaries on the backend for roster data.
- In the frontend, parse date-only values deliberately (for example,
  `new Date("${date}T00:00:00")`) to avoid timezone shifts.
- Use `date-fns` for formatting and date arithmetic. Do not write a new date
  parser for each feature.
- Do not assume the browser timezone matches the roster timezone.

### 2.8 PWA and offline behaviour

- Keep the PWA scope to installability, manifest, icons, and shell caching for
  the MVP.
- Never cache authenticated API responses or roster data in the service worker
  unless offline support is explicitly designed and tested.
- Keep `/api` out of the navigation fallback, as the current Vite PWA config
  does.
- Treat offline editing and background sync as post-MVP work.

### 2.9 Frontend testing

- Use Vitest + React Testing Library for component and utility tests.
- Test behaviour and user-visible outcomes, not implementation details.
- Prioritise tests for date utilities, status mapping, grid rendering,
  validation, permission-sensitive UI, and mutation error handling.
- Keep Playwright for end-to-end flows that cross frontend and backend. Avoid
  duplicating every unit-level case there.
- Test at least one mobile viewport for the roster experience.
- Do not use arbitrary sleeps in E2E tests. Wait for visible state or network
  responses that the test actually depends on.

---

## 3. Backend practices

### 3.1 Structure and responsibilities

- Keep the layering clear:
  - `api/v1/` — HTTP routing, dependencies, status codes, response models.
  - `schemas/` — Pydantic request/response contracts.
  - `services/` — business rules and orchestration.
  - `models/` — SQLAlchemy persistence models.
  - `db/` — engine/session, D1 binding helpers, and base setup.
  - `core/` — request-scoped settings, security, shared infrastructure.
  - `workers/` — Durable Object classes for crypto, rate limiting, generation,
    and rendering.
- **Route handlers stay thin.** They parse input, resolve dependencies,
  authorize, call a service, and return a typed response. Business rules belong
  in services.
- **Services should not depend on FastAPI request objects.** Keep domain logic
  callable and testable with a database session and plain values.
- **Respect the Worker runtime.** Normal API work must fit the CPU budget and
  stay within the D1 query limit; use `db.batch()` and offload CPU-heavy work to
  a Durable Object when needed.
- **Use the D1 helpers.** Worker queries go through `app/db/d1.py` rather than a
  second connection path, so batching, bound-parameter limits, and result
  conversion stay in one place.
- **Models are persistence, not API contracts.** Do not return ORM objects
  directly from endpoints; convert through Pydantic response models.
- Use dependency injection (`DbSession`, `CurrentUser`, `AdminUser`,
  `csrf_protect`) rather than reaching for global state.
- Prefer small, named functions over long route handlers or deeply nested
  conditionals.

### 3.2 Python style and typing

- Target Python 3.12+ as configured in `pyproject.toml`.
- Use modern type syntax (`str | None`, `list[str]`, built-in generics).
- Add type hints to public functions and service boundaries. Complex data
  structures should have named types or explicit shapes.
- Keep line length at the configured 100 characters.
- Run Ruff before committing:

  ```bash
  cd backend
  uv run ruff check .
  uv run ruff format .
  ```

- Prefer explicit, descriptive names over abbreviations. Domain terms such as
  `roster_period`, `employee_code`, `shortage`, and `rotation_offset` should be
  used consistently.
- Avoid broad `except Exception` blocks. Handle known failure modes and let
  unexpected errors surface with useful context. The password verifier is a
  deliberate exception because hash verification failures must not leak
  details.

### 3.3 Validation and schemas

- Validate every incoming request with Pydantic schemas. Do not read raw
  dictionaries from request bodies.
- Use constrained types and `Field` validation for ranges, lengths, and
  formats (year, month, year-month consistency, date ranges, codes).
- Keep request, response, and internal models distinct where their concerns
  differ.
- Return the same shape for the same resource across endpoints.
- Validate cross-field rules explicitly (for example, start date must not be
  after end date, assignment date must belong to the roster month).
- Never trust a client-supplied role or identity. Resolve the current user from
  the session on the server.

### 3.4 Database and transactions

- Always access the database through the async `get_db` dependency; it reads
  the `DB` binding from the Worker request scope and closes the session.
- Use SQLAlchemy 2 style (`select`, `db.scalars`, `db.get`, typed mapped
  columns).
- Keep queries explicit and readable. Avoid N+1 queries on roster-sized data;
  load related records deliberately.
- Wrap multi-row updates in a transaction and validate the whole request before
  applying any part of it. D1 has no interactive transactions, so group the
  statements in `d1_batch()`; the batch is atomic and counts as one query.
- Commit once per logical operation. Do not commit halfway through a service
  operation that must be atomic.
- Batch bulk writes through D1's `batch()` API (`app/db/d1.py`) so a request
  issues a small, bounded number of queries instead of one per row.
- Pass prepared statements directly to `env.DB.batch()` through `d1_batch()`.
  Do not convert them with `to_js()`; the resulting borrowed Pyodide proxies are
  destroyed before the batch completes.
- Keep each statement under D1's 100-bound-parameter limit; `chunk_rows()` and
  `multi_row_insert()` already split large inserts into safe statements.
- Use database constraints as a second line of defence: unique employee codes,
  one assignment per employee/day, one published roster per month, foreign
  keys, and appropriate indexes.
- Use `DATE` for roster dates and store timestamps as UTC text in D1, parsing
  them back to aware values in the application.
- Soft-delete employees (`is_active = false`) so historical rosters remain
  accurate.

### 3.5 Migrations

- Every production schema change ships with a numbered SQL migration in
  `backend/migrations/d1/`.
- Apply migrations with `npx wrangler d1 migrations apply octopod --local` or
  `--remote`; never edit an already-applied migration in a shared environment.
- Keep `scripts/check_d1_schema.py` passing so the SQL migrations and
  SQLAlchemy metadata stay aligned.
- Keep each migration within D1's SQL limits. D1 rejects some large compound
  `SELECT` statements that local SQLite accepts, so use a recursive CTE or split
  the work, and test against a staging D1 database.
- Test migrations against a fresh local D1 database and, where relevant, an
  existing populated database.
- Keep migration filenames descriptive and ordered.

### 3.6 Configuration and secrets

- Read configuration through request-scoped settings from
  `app/core/config.py` (`get_settings(env)`); do not scatter `os.getenv()`
  calls.
- Non-secret Worker configuration lives in the `vars` block of
  `backend/wrangler.jsonc`. The local Worker reads `backend/.dev.vars`; commit
  only `.dev.vars.example`.
- Store production secrets with `wrangler secret put` (notably `SECRET_KEY`).
- Use a long random `SECRET_KEY` outside development and set `COOKIE_SECURE=true`
  behind HTTPS.
- Do not log secrets, passwords, session tokens, CSRF tokens, or full cookie
  values.
- Restrict CORS to known origins; do not use wildcard origins with credentials.
- Rate limiting is backed by the `RateLimiter` Durable Object so it is shared
  across Worker isolates; use the existing limiter rather than adding
  in-process state.

### 3.7 Error handling and HTTP semantics

- Raise `HTTPException` with a clear, non-sensitive `detail` for expected
  failures.
- Use appropriate status codes consistently:
  - `200` — successful read or update.
  - `201` — resource created.
  - `204` — successful delete with no body.
  - `400` — malformed or invalid request data.
  - `401` — not authenticated.
  - `403` — authenticated but not allowed.
  - `404` — resource not found or not visible to the caller.
  - `409` — state conflict (editing a published roster, duplicate draft
    conditions).
  - `422` — schema validation failure (FastAPI default).
  - `429` — rate limited.
- Avoid leaking whether a protected resource exists to users who cannot access
  it. Prefer `403` or `404` consistently for the relevant endpoint.
- Never return stack traces or internal exception text to clients.

### 3.8 Backend testing

- Use pytest with the existing fixtures and an isolated temporary SQLite test
  database for the fast suite, plus D1 helper tests and optional `d1`-marked
  integration tests against `pywrangler dev`.
- Cover the D1 helpers directly, including prepared-statement batching, because
  that code only runs inside the Worker runtime.
- Keep tests independent and deterministic. Do not rely on execution order or
  shared mutable state.
- Cover the domain rules directly, not only through HTTP:
  - generation excludes leave, comp-off, and unavailable dates, and applies
    each employee's chosen consecutive week-off pair;
  - no employee has two statuses on the same day;
  - holidays apply to everyone;
  - staffing shortages are reported;
  - generation is deterministic for identical inputs;
  - published rosters are immutable;
  - versioning and archival behave correctly.
- Cover API behaviour: authentication, role enforcement on every protected
  route, CSRF enforcement, validation errors, publish rules, and export
  permissions.
- Use `httpx`/`TestClient` and assert status codes plus response shape.
- Keep test data minimal but realistic. Prefer factory/helper functions over
  copying large JSON blobs.
- Run the full backend suite before merging:

  ```bash
  cd backend
  uv run pytest
  ```

---

## 4. API design practices

- Keep all application endpoints under `/api/v1`.
- Use resource-oriented REST paths and standard HTTP methods.
- Use plural nouns for collections (`/employees`, `/rosters`), and nested paths
  only for genuinely owned resources.
- Keep request and response schemas explicit and documented through FastAPI's
  OpenAPI output at `/api/docs`.
- Return consistent error bodies. FastAPI's `{"detail": ...}` shape is the
  default; the frontend client already understands it.
- Validate query parameters with constraints (`ge`, `le`, required filters)
  rather than accepting arbitrary values.
- Do not expose draft rosters to employees. Authorization must be enforced on
  every route, including export and self-view endpoints.
- Keep the employee lookup response minimal (`employee_code`, `full_name`) and
  rate-limit it. Lookup must never authenticate or reveal private data.
- Prefer explicit actions (`/publish`, `/generate`, `/deactivate`) over
  overloading a generic update when the action has distinct business rules.
- When changing an existing contract, update the frontend client/types and
  tests in the same change.

---

## 5. Authentication, authorization, and security

- Hash passwords with Argon2id through the shared security helpers, which
  offload hashing and verification to the `CryptoBox` Durable Object. Never
  store or log plaintext passwords.
- Use HttpOnly session cookies for browser authentication. Do not put session
  tokens in `localStorage`.
- Require the `X-CSRF-Token` header for cookie-authenticated mutations, through
  the existing `csrf_protect` dependency.
- Enforce role checks server-side using `CurrentUser` / `AdminUser`. Frontend
  guards are UX only.
- Apply deny-by-default to new endpoints. If an endpoint is not explicitly
  public, require authentication.
- Rate-limit login and employee-ID lookup. Keep error messages generic enough
  to avoid account or employee enumeration.
- Validate and authorise before performing expensive work such as export
  rendering.
- Export only the roster version the caller is allowed to see. Employees must
  never export drafts.
- Treat all user input as untrusted, including IDs in paths and dates in query
  strings.
- Keep dependencies reasonably current, but do not introduce major upgrades
  during MVP hardening without a clear need and a test pass.

---

## 6. Roster domain practices

- Roster generation is backend-owned, deterministic, and testable.
- Keep the generator a straightforward heuristic until the rules genuinely
  justify an optimiser. Do not add an optimisation library speculatively.
- Never silently ignore constraints. Return structured shortages and warnings
  for administrator review.
- Never auto-publish a generated roster. Publishing is always an explicit
  administrator action.
- Treat published versions as immutable snapshots. Create a new draft/version
  to make changes; archive the previous published version.
- Use the fixed-shift rotation and fairness counters consistently. Document
  any change to the shift, week-off, or selection rules in `docs/decisions.md`.
- Read status codes and labels from the database. Do not hard-code domain
  statuses in unrelated presentation code.
- Keep assignment uniqueness and month-boundary validation in both service
  logic and database constraints where possible.
- Keep generation audit information (shortages, warnings, actor, timestamp)
  so administrators can understand what happened.
- Prefer deterministic tie-breaking (for example, employee ID) so identical
  inputs produce identical rosters.

---

## 7. MVP practices

### 7.1 Scope discipline

The MVP is the coherent slice described in [`GOAL.md`](./GOAL.md): an
administrator can manage employees and availability, generate and edit a monthly
roster, publish it, and export a PNG; an employee can authenticate and view the
published roster; critical rules are covered by automated tests.

- Build only what is needed to complete that slice.
- Defer offline editing, native apps, swap workflows, notifications, email
  delivery, payroll integration, multi-tenancy, i18n, and analytics dashboards.
- Do not add infrastructure (Kubernetes, message brokers, microservices, a
  complex CI/CD platform) that the MVP does not need.
- If a new requirement appears, ask: does it change the MVP definition of done?
  If not, record it as a follow-up rather than expanding the current change.
- Prefer one working vertical slice over several half-finished layers.

### 7.2 Build order

Work in vertical slices that end in something demonstrable:

1. Data model + migration + service rule.
2. API endpoint + validation + tests.
3. Typed frontend client + UI state.
4. User-visible screen + error/empty/loading states.
5. End-to-end test for the critical path.

A slice is not done when the happy path works only by hand.

### 7.3 Quality bar for MVP

Every MVP feature should meet this bar before being considered complete:

- **Works end-to-end** on desktop and a mobile-width viewport.
- **Authorization tested**: employees cannot perform admin actions, and drafts
  are not exposed to employees.
- **Validation tested**: invalid dates, statuses, and conflicting assignments
  fail clearly.
- **Failure states handled**: loading, empty, error, and conflict states are
  visible and understandable.
- **Data integrity protected**: relevant unique constraints and transaction
  boundaries exist.
- **Accessible enough**: keyboard usable, labelled controls, status not
  communicated by colour alone.
- **Tested**: unit/API tests for rules, component tests for risky UI, and an
  E2E test for the primary flow.
- **Documented**: README or decisions doc updated when behaviour or setup
  changes.

### 7.4 Definition of done (MVP)

The MVP is complete when all of the following are true:

- [ ] An administrator can create, edit, and deactivate employees.
- [ ] Employee codes are unique, and public lookup shows only the matching name
      and never grants access.
- [ ] Administrators can record leave, comp-off, and unavailable dates, and
      choose each employee's consecutive week-off days.
- [ ] An administrator can create a month, generate a draft, review shortages,
      edit any cell, and publish only with explicit confirmation.
- [ ] Published rosters are immutable, versioned, and visible to employees;
      drafts are not.
- [ ] Employees can view the published roster with their own row highlighted
      and no editing capability.
- [ ] PNG export includes month, dates, employee names, statuses, and the
      legend, and respects permissions.
- [ ] Authentication uses secure cookies, CSRF protection, Argon2id hashing,
      and server-enforced roles.
- [ ] Backend, frontend, and Playwright tests cover the critical flows and pass.
- [ ] The app is installable as a PWA and usable on modern mobile and desktop
      browsers.
- [ ] Setup, environment variables, migrations, and deployment are documented
      in the README.

### 7.5 Things to avoid in the MVP

- Premature generic abstractions ("framework" code, plugin systems, complex
  base classes).
- A global frontend state store for server data.
- Client-side-only authorization.
- Silent constraint failures or auto-publishing.
- Manual schema changes without migrations.
- Caching authenticated data in the service worker.
- New dependencies for trivial utilities that the standard library, existing
  packages, or a few lines of code can handle.
- Broad refactors unrelated to the current slice.
- Copy-pasting status colours or business rules instead of using shared data.

### 7.6 When to iterate after MVP

Collect real usage feedback before adding complexity. Good candidates for the
first iteration are:

- Shift swaps and employee requests.
- Notifications and email delivery.
- Richer fairness history across months.
- Offline read-only roster access.
- More export layouts or pagination for very large teams.
- Audit/analytics dashboards.

Do not build these until the MVP is stable and the need is demonstrated.

---

## 8. Code review checklist

Use this for every non-trivial change.

**Correctness**

- [ ] The change matches the stated requirement and does not expand scope
      unnecessarily.
- [ ] Edge cases are handled: empty data, invalid dates, duplicate entries,
      inactive employees, shortages, published rosters.
- [ ] State transitions are valid (draft → published → archived) and enforced
      server-side.

**Security**

- [ ] New endpoints require the correct role and CSRF protection where
      applicable.
- [ ] Inputs are validated on the backend.
- [ ] No secrets, tokens, or sensitive data are logged or committed.
- [ ] Export and read endpoints do not leak drafts or unauthorized data.

**Data**

- [ ] Schema changes include a migration.
- [ ] Multi-row writes are transactional.
- [ ] Constraints and indexes support the new access patterns.
- [ ] Historical and published data remain intact.

**Frontend**

- [ ] Server state goes through TanStack Query and the shared API client.
- [ ] Loading, empty, error, and disabled states are handled.
- [ ] The UI is keyboard accessible and works at mobile width.
- [ ] Types are accurate; no `any` or weakened compiler settings.

**Tests**

- [ ] Domain rules and API permissions are covered.
- [ ] Risky UI behaviour is covered.
- [ ] The primary user flow remains covered by E2E.
- [ ] The full suites pass locally.

**Docs and operations**

- [ ] README or `docs/decisions.md` is updated for changed behaviour or setup.
- [ ] Environment variables are reflected in `wrangler.jsonc` vars and
      `backend/.dev.vars.example`.
- [ ] Deployment impact is understood (migrations, secrets, backups, HTTPS).

---

## 9. Documentation practices

- Keep README setup instructions runnable from a clean checkout.
- Record product and architectural decisions in `docs/decisions.md`, including
  the reason and the consequence.
- Update `TECH_STACK.md` when the stack changes; update this file when team
  conventions change.
- Document non-obvious domain rules next to the code that implements them and
  in the decisions log.
- Prefer concrete examples and commands over abstract guidance.
- Keep documentation in sync with behaviour. Stale docs are worse than no docs.

---

## 10. Local commands and quality gates

Run these before committing or opening a pull request.

```bash
# Backend
cd backend
uv sync
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_d1_schema.py
uv run pytest
uv run python -m py_compile src/worker.py src/app/workers/*.py
uv run pywrangler deploy --dry-run

# Frontend
cd frontend
npm install
npm test
npm run typecheck
npm run build

# End-to-end (Chromium installed once)
cd frontend
npx playwright install chromium
npx playwright test
```

### Database changes

Add a numbered SQL migration under `backend/migrations/d1/`, then apply it:

```bash
cd backend
npx wrangler d1 migrations apply octopod --local
npx wrangler d1 migrations apply octopod --remote
uv run python scripts/check_d1_schema.py
```

Never edit an already-applied migration. Add a new migration that is
backward-compatible for at least one deploy, because a Worker rollback does not
roll back D1.

### Minimal pre-merge gate

At minimum, the following must pass for any change that touches application
behaviour:

- [ ] `uv run ruff check .`
- [ ] `uv run python scripts/check_d1_schema.py`
- [ ] `uv run pytest`
- [ ] `npm run typecheck`
- [ ] `npm test`
- [ ] `npm run build`

Add the relevant Playwright test when the change affects a critical user flow.
