# TECH_STACK.md

## Overview

This document defines the technology stack for the roster management
application. The application is a responsive Progressive Web App (PWA)
served by a single Cloudflare Worker: Static Assets delivers the React
build, `workers.asgi` runs the FastAPI application under `/api/*`, D1
stores data, and Durable Objects handle CPU-heavy or stateful work. It
should be straightforward to develop and run on Linux Mint, with no
requirement for a Mac or complex infrastructure.

## 1. Frontend

  -----------------------------------------------------------------------
  Area                    Technology              Purpose
  ----------------------- ----------------------- -----------------------
  Framework               React                   Build the application
                                                  interface

  Language                TypeScript              Add static typing and
                                                  improve maintainability

  Build tool              Vite                    Local development and
                                                  production builds

  Styling                 Tailwind CSS            Responsive styling

  UI components           shadcn/ui               Accessible, reusable
                                                  interface components

  Routing                 React Router            Navigate between
                                                  application pages

  Server state            TanStack Query          Fetch, cache, and
                                                  update backend data

  Forms                   React Hook Form         Manage forms

  Validation              Zod                     Validate frontend form
                                                  data

  PWA                     vite-plugin-pwa         Web app manifest,
                                                  service worker, and
                                                  installability
  -----------------------------------------------------------------------

### Frontend requirements

-   Use a responsive layout suitable for mobile phones, tablets, and
    desktop browsers.
-   Use TypeScript throughout the frontend.
-   Keep API communication in a dedicated service/API layer.
-   Keep UI components reusable and avoid unnecessary abstractions.
-   Use TanStack Query for data received from the backend.
-   Use local component state for simple UI interactions; add a global
    state library only if a real need arises.
-   Implement the PWA manifest, icons, and service worker.
-   Do not assume that all browser capabilities are identical across
    Android, iOS, and desktop.
-   Treat offline support as a later enhancement unless a specific
    feature requires it.

## 2. Backend

  -----------------------------------------------------------------------
  Area                    Technology              Purpose
  ----------------------- ----------------------- -----------------------
  Language                Python                  Backend implementation

  API framework           FastAPI                 REST API

  Data validation         Pydantic                Validate API requests
                                                  and responses

  ORM                     SQLAlchemy              Database access and
                                                  object-relational
                                                  mapping

  Worker runtime          workers-py              Adapt FastAPI (ASGI) to
                                                  the Cloudflare fetch
                                                  handler and Durable Objects

  Migrations              Wrangler D1 migrations  Version and apply the D1
                                                  schema

  Database driver         sqlalchemy-cloudflare-d1 SQLAlchemy dialect for D1

  Testing                 pytest                  Backend automated tests

  Code quality            Ruff                    Python linting and
                                                  formatting

  Python environment      uv                      Dependency and
                                                  virtual-environment
                                                  management
  -----------------------------------------------------------------------

### Backend requirements

-   Expose a versioned REST API under `/api/v1`.
-   Keep business logic separate from API route handlers.
-   Validate all incoming data on the backend.
-   Enforce authorization on the backend; frontend role checks alone are
    not security.
-   Keep database access behind clear service or repository boundaries.
-   Use atomic batch operations for updates that touch related roster records.
-   Generate API documentation through FastAPI's OpenAPI support.
-   Store secrets and environment-specific configuration outside source
    code.

## 3. Database

**Cloudflare D1** (SQLite) is the primary database. Local development and
the pytest suite use a plain SQLite file through the same SQLAlchemy
models; the D1 dialect is selected when the Worker supplies the `DB`
binding.

It will store:

-   Employee records and unique employee IDs.
-   User accounts, authentication data, and roles.
-   Employee availability and leave records.
-   Roster periods.
-   Daily employee shift assignments.
-   Shift/status definitions and applicable staffing requirements.
-   Roster publication state and relevant audit information.

Use SQLAlchemy for database access. The production schema is owned by the
SQL migrations in `backend/migrations/d1/`, applied with
`wrangler d1 migrations apply`. Batch writes through D1's `batch()` API so a
request does not issue one round trip per row and stays within the Worker's
query budget.

`app/db/d1.py` centralises the Worker-specific helpers. It prepares statements,
keeps each statement under D1's 100-bound-parameter limit, and passes prepared
statements directly to `DB.batch()`; do not convert them with `to_js()`, whose
borrowed proxies do not survive the call. D1 also enforces stricter SQL limits
than local SQLite, so large reference-data migrations use recursive CTEs or
several statements.

Store dates using appropriate date types and timestamps. D1 has no
native timezone-aware type, so timestamps are stored as UTC text and
parsed back to timezone-aware values in the application. Enforce
important data integrity rules through database constraints as well as
application validation.

## 4. Authentication and Authorization

-   Support administrator and employee roles.
-   Use secure password-based authentication for accounts.
-   Use employee ID lookup only to identify an employee and display
    their associated name before authentication.
-   An employee ID alone must never grant access to an account or
    private roster information.
-   Use secure, HttpOnly cookies for browser authentication where
    practical.
-   Apply appropriate CSRF protection when cookie-based authentication
    is used.
-   Enforce role-based permissions on every protected backend operation.
-   Do not store passwords in plain text; use a modern password-hashing
    algorithm such as Argon2id.
-   Provide a secure way for administrators to create or deactivate
    employee accounts.

## 5. Roster Generation

Roster generation will initially be implemented as backend application
logic in Python.

It should:

-   Accept the roster month, active employees, availability, approved
    leave, and staffing requirements.
-   Respect configured scheduling constraints.
-   Avoid conflicting assignments and assignments during approved leave.
-   Distribute shifts and days off fairly where possible.
-   Report staffing shortages and unsatisfied constraints.
-   Return a draft roster for administrator review.
-   Require administrator approval before publication.

Start with a straightforward, testable scheduling algorithm. Introduce a
dedicated optimization library only if the scheduling rules become too
complex for a maintainable application-level solution.

The pure computation runs inside the Worker because it is small and
deterministic. A `Generator` Durable Object is available for deployments
whose rosters are large enough to approach the Worker CPU limit; the default
path keeps generation in-process.

## 6. Image Export

Generate roster images from the rendered roster view or from a dedicated
export layout.

The exported image should include:

-   Roster month and year.
-   Employee names.
-   Dates and days.
-   Shift/status labels.
-   A status legend.

The export must remain readable at common sharing and printing sizes.
The export should represent the selected roster version and should not
expose information the requesting user is not authorized to view.

Rendering happens in the browser with the Canvas 2D API
(`frontend/src/lib/export.ts`) and produces a PNG blob that the browser
downloads. This keeps image encoding out of the Worker CPU budget and
works offline once the roster is loaded. The server-side
`GET /rosters/{id}/export.png` endpoint is retained for API compatibility and
delegates to the `Renderer` Durable Object when it is bound.

## 7. API and Application Communication

-   Use JSON over HTTPS for frontend/backend communication.
-   Use REST endpoints under `/api/v1`.
-   Keep request and response schemas explicit.
-   Return consistent HTTP status codes and error response formats.
-   Configure the frontend with the backend API base URL through
    environment configuration.
-   Prefer serving the frontend and API under the same site origin in
    production, for example `/` for the frontend and `/api` for the
    backend.

## 8. Development and Testing

The application must be developable on Linux Mint.

Required local tools:

-   Git
-   Node.js and npm
-   Python 3.12+ and uv
-   Wrangler / `pywrangler` for local Worker and D1 development
-   A modern browser with developer tools

SQLite is used directly for the fast pytest path; no external database server
is required.

Testing tools:

  Area                         Technology
  ---------------------------- -----------------------
  Backend unit and API tests   pytest
  Frontend unit tests          Vitest
  UI/component tests           React Testing Library
  Browser end-to-end tests     Playwright

Important test coverage includes:

-   Employee ID uniqueness and lookup behavior.
-   Authentication and role-based access.
-   Employee read-only permissions.
-   Leave and availability validation.
-   Shift assignment conflicts.
-   Staffing requirement validation.
-   Roster generation constraints and fairness expectations.
-   Draft review and publication.
-   Roster image export.

## 9. Deployment

Keep deployment simple: one Cloudflare Worker serves everything.

-   `uv run pywrangler deploy` builds and publishes the Python Worker;
    Static Assets serves `frontend/dist`.
-   D1 is the production database; apply migrations with
    `wrangler d1 migrations apply octopod --remote`.
-   Durable Objects (`CryptoBox`, `RateLimiter`, `Generator`, `Renderer`)
    are declared in `wrangler.jsonc` and migrated alongside the Worker.
-   Secrets (`SECRET_KEY`) live in `wrangler secret put`, never in Git.
    Non-secret configuration lives in the `vars` block.
-   Export D1 regularly (`wrangler d1 export`) and keep copies outside
    Cloudflare.
-   Use HTTPS; Cloudflare terminates TLS. Keep the session cookie
    `Secure` and `SameSite=Lax`.
-   Do not introduce Kubernetes, microservices, message brokers, or a
    complex CI/CD platform for the initial version.

## 10. Repository Structure

Use a single Git repository (monorepo) for the application.

``` text
roster-management/
├── frontend/
│   ├── public/
│   └── src/
├── backend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── core/
│   │   │   ├── db/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── services/
│   │   │   ├── workers/ # Durable Object classes
│   │   │   └── main.py
│   │   └── worker.py    # Worker entrypoint (Default = asgi.entrypoint)
│   ├── migrations/
│   │   └── d1/          # D1 SQL migrations (production schema)
│   ├── wrangler.jsonc   # Worker, D1, DO, and Static Assets config
│   ├── .dev.vars.example # Local Worker secrets and vars
│   └── tests/
├── docs/
├── .gitignore
└── README.md
```

The exact internal structure may evolve as the application grows, but
the frontend and backend should remain clearly separated.

## 11. Guiding Technical Principles

-   Prefer simple, proven technologies over unnecessary infrastructure.
-   Keep the frontend independent of backend implementation details.
-   Keep business rules and roster-generation logic in the backend.
-   Keep the API and database reusable if a native mobile client is
    introduced later.
-   Prioritize security, data integrity, accessibility, and
    maintainability.
-   Avoid adding dependencies or services without a clear requirement.
