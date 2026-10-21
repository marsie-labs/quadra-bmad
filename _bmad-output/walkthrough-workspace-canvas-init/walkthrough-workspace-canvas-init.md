# Walkthrough: Workspace and Realtime Canvas Initialization

Target: commit a0882e3

- [x] **Block 1 — Intent**
- [x] **Block 2 — Broad Strokes**
- [x] **Block 3 — Session & Canvas Creation**
- [x] **Block 4 — Data Layer**
- [x] **Block 5 — Realtime Subscription**
- [x] **Block 6 — Periphery**

---

## Block 1 — Intent

*Source: plan frozen intent section*

**Problem:** The quadra project has no backend — teams cannot create collaborative sessions, initialize a four-quadrant IS / IS NOT / DOES / DOES NOT canvas, or share real-time state with other participants.

**Approach:** Build a FastAPI backend that creates sessions backed by Supabase PostgreSQL, instantiates all four canvas quadrants on session creation, provisions Supabase Realtime on the workspaces table via supabase-py, and exposes sessions via shareable link tokens (no auth required).

---

## Block 2 — Broad Strokes

Four entry points:

1. [`app/main.py`](../../app/main.py) — FastAPI app factory; lifespan handler starts the realtime background task on startup and cancels it on shutdown
2. [`app/routers/sessions.py:17`](../../app/routers/sessions.py) — two public endpoints: `POST /sessions` creates workspace + canvas + quadrants; `GET /sessions/{access_token}` retrieves full canvas state by link token
3. [`supabase/migrations/001_init.sql`](../../supabase/migrations/001_init.sql) — DDL for all three tables plus the two Realtime enablement statements
4. [`app/realtime.py`](../../app/realtime.py) — supabase-py channel subscription on the `workspaces` table, running as a persistent asyncio task that logs INSERT/UPDATE events server-side

---

## Block 3 — Session & Canvas Creation

[`app/routers/sessions.py`](../../app/routers/sessions.py) owns both endpoints.

`POST /sessions` ([line 17](../../app/routers/sessions.py)) runs four sequential Supabase inserts: workspace row → canvas row → four quadrant rows (one per `QuadrantType` enum value) → re-fetch quadrants to build the response. No transaction wrapper — a mid-flight failure leaves an orphaned workspace; the review pass patched `GET` to guard against a missing canvas (HTTP 500 if canvas absent).

`GET /sessions/{access_token}` ([line 61](../../app/routers/sessions.py)) looks up the workspace by `access_token` (the public UUID), raises 404 if absent, then fetches canvas and quadrants assembling the same `SessionResponse` shape. Both handlers build `access_url` from `request.base_url` so the URL is environment-agnostic.

Key types: [`QuadrantType` enum](../../app/models.py) drives the four-row insert; [`SessionResponse`](../../app/models.py) is the shared return shape for both endpoints.

---

## Block 4 — Data Layer

[`app/config.py`](../../app/config.py) — pydantic-settings `Settings` reads `SUPABASE_URL` and `SUPABASE_KEY` from env; the module-level `settings` singleton is instantiated at import time, so a missing env var fails fast on startup.

[`app/database.py`](../../app/database.py) — lazy `AsyncClient` singleton. `get_client()` creates the supabase-py async client on first call and caches it; every route handler calls this.

[`app/models.py`](../../app/models.py) — `QuadrantType(str, Enum)` with values `IS`, `IS_NOT`, `DOES`, `DOES_NOT` is the single source of truth for quadrant names across DB, application, and API. `SessionCreate` uses a `@field_validator` to reject blank/whitespace-only names. `SessionResponse → CanvasState → list[QuadrantOut]` is the shared nested response shape.

---

## Block 5 — Realtime Subscription

[`app/realtime.py`](../../app/realtime.py) wires supabase-py's realtime channel to a persistent asyncio background task.

[`_listen()`](../../app/realtime.py) opens a channel named `"workspace-realtime"`, registers `_handle_change` as the callback for all postgres change events on `public.workspaces`, calls `await channel.subscribe()`, then parks on `asyncio.Event().wait()` — holding the task alive without spinning. On `CancelledError` (shutdown) it calls `channel.unsubscribe()` before re-raising.

[`subscribe()`](../../app/realtime.py) wraps `_listen()` in `asyncio.create_task()` with a done-callback that logs unexpected exceptions. [`app/main.py`](../../app/main.py) calls it in the lifespan startup block and cancels the task on teardown.

[`_handle_change`](../../app/realtime.py) extracts `eventType` and the new row's `id` and logs them. The migration enables `REPLICA IDENTITY FULL` on `workspaces` ([001_init.sql:30](../../supabase/migrations/001_init.sql)) so UPDATE events carry the full new row.

---

## Block 6 — Periphery

- [`pyproject.toml`](../../pyproject.toml) — project declared as `quadra`; runtime deps: `fastapi>=0.115`, `supabase>=2.9`, `uvicorn[standard]>=0.32`, `pydantic-settings>=2.6`; dev deps: `pytest`, `pytest-asyncio`, `httpx`
- [`uv.lock`](../../uv.lock) — locked dependency tree
- [`.env.example`](../../.env.example) — three required env vars: `SUPABASE_URL`, `SUPABASE_KEY`, `PORT`
- [`tests/test_sessions.py`](../../tests/test_sessions.py) — 6 tests covering all five I/O matrix rows; mocks Supabase client and realtime subscription so no live credentials needed
- `app/__init__.py`, `app/routers/__init__.py`, `tests/__init__.py` — package markers
