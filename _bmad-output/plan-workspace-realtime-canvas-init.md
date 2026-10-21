---
title: 'Workspace and Realtime Canvas Initialization'
type: 'feature'
ticket: ''
created: '2026-10-21'
status: 'built'
baseline_revision: 'NO_VCS'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The quadra project has no backend — teams cannot create collaborative sessions, initialize a four-quadrant IS / IS NOT / DOES / DOES NOT canvas, or share real-time state with other participants.

**Approach:** Build a FastAPI backend that creates sessions backed by Supabase PostgreSQL, instantiates all four canvas quadrants on session creation, provisions Supabase Realtime on the workspaces table via supabase-py, and exposes sessions via shareable link tokens (no auth required).

## Boundaries & Constraints

**Always:** Use supabase-py for all Supabase interactions; generate a UUID-based `session_id` per workspace; each session owns exactly one canvas with exactly four quadrant rows (IS, IS_NOT, DOES, DOES_NOT); link access uses a separate `access_token` (UUID) embedded in the share URL; the workspaces table must have Realtime enabled.

**Never:** No user authentication (OAuth, JWT, cookie sessions); no per-quadrant content editing in this scope (initialization only); no frontend implementation; no multi-tenancy or workspace ownership model.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Create session | `POST /sessions` `{"project_name": "MyProject"}` | 201 — workspace + canvas + 4 quadrants created; returns `session_id`, `access_token`, `access_url` | 422 if `project_name` missing or blank |
| Access via link | `GET /sessions/{access_token}` | 200 — full workspace + canvas + quadrant state as JSON | 404 if token unknown |
| Realtime event | Any write to `workspaces` row | Supabase Realtime emits INSERT/UPDATE to all channel subscribers | Supabase handles delivery; server logs errors |
| Duplicate name | `POST /sessions` with a name already in use | New session created with new IDs (names are non-unique) | No error |
| Blank name | `POST /sessions` `{"project_name": ""}` | 422 validation error | Pydantic `min_length=1` enforces it |

</frozen-after-approval>

## Code Map

New project — no existing code. Files to create:

- `pyproject.toml` — project metadata and deps: fastapi, supabase, uvicorn[standard], python-dotenv, pydantic-settings
- `.env.example` — required env var template: SUPABASE_URL, SUPABASE_KEY, PORT
- `app/__init__.py` — package marker
- `app/config.py` — pydantic-settings `Settings` class; reads env vars; exported singleton `settings`
- `app/database.py` — supabase-py async `AsyncClient` singleton initialized from `settings`
- `app/models.py` — Pydantic schemas: `SessionCreate`, `SessionResponse`, `CanvasState`, `QuadrantOut`; `QuadrantType` enum with IS / IS_NOT / DOES / DOES_NOT values
- `app/routers/sessions.py` — `POST /sessions`: inserts workspace, canvas, 4 quadrants; `GET /sessions/{access_token}`: returns full state
- `app/realtime.py` — supabase-py realtime subscription on `workspaces` table; logs change events server-side; exposes `subscribe()` coroutine for startup
- `app/main.py` — FastAPI app factory; includes sessions router; lifespan handler calls `realtime.subscribe()` on startup
- `supabase/migrations/001_init.sql` — `workspaces`, `canvases`, `quadrants` DDL; `ALTER TABLE workspaces REPLICA IDENTITY FULL`; adds `workspaces` to `supabase_realtime` publication

## Tasks & Acceptance

**Execution:**
- [x] `supabase/migrations/001_init.sql` — Create all three tables with FK constraints; set REPLICA IDENTITY FULL on workspaces; add workspaces to supabase_realtime publication
- [x] `pyproject.toml` — Declare project with fastapi, supabase, uvicorn[standard], python-dotenv, pydantic-settings deps
- [x] `.env.example` — Document SUPABASE_URL, SUPABASE_KEY, PORT
- [x] `app/config.py` — pydantic-settings Settings; validate SUPABASE_URL and SUPABASE_KEY are non-empty
- [x] `app/database.py` — Initialize supabase async client once; expose `get_client()` for use in route handlers
- [x] `app/models.py` — QuadrantType enum; Pydantic request/response schemas for session create and canvas state
- [x] `app/routers/sessions.py` — POST /sessions creates workspace + canvas + 4 quadrants in order; GET /sessions/{access_token} fetches and assembles full state
- [x] `app/realtime.py` — Open supabase-py realtime channel on `workspaces`; subscribe to INSERT/UPDATE; log events; run in background task
- [x] `app/main.py` — Assemble app; lifespan starts realtime subscription; include sessions router

**Acceptance Criteria:**
- Given a POST to /sessions with a non-empty `project_name`, when the request completes, then a `workspaces` row exists with a unique `session_id` (UUID) and `access_token` (UUID), a `canvases` row linked to it, and exactly four `quadrants` rows (IS, IS_NOT, DOES, DOES_NOT) linked to the canvas.
- Given an `access_token` returned from session creation, when `GET /sessions/{access_token}` is called, then HTTP 200 returns `session_id`, `project_name`, `canvas_id`, and all four quadrants.
- Given an unknown `access_token`, when `GET /sessions/{access_token}` is called, then HTTP 404 is returned.
- Given the server starts with valid Supabase credentials, when a workspace INSERT occurs, then the server-side realtime handler logs the event without crashing.
- Given Realtime is enabled on the `workspaces` table, when a workspace is inserted, then a supabase-py subscriber receives the change event (verified by server log output).

## Implementation Notes

Added `tests/test_sessions.py` (6 tests) and dev deps (`pytest`, `pytest-asyncio`, `httpx`) to satisfy the I/O Matrix audit — all 6 tests pass. Also added `app/routers/__init__.py` and `app/__init__.py` as package markers; `tests/__init__.py` likewise. The `_IncludedRouter` FastAPI v0.115+ routing object holds the sessions router — routes resolve correctly at runtime despite not appearing as `APIRoute` instances in `app.routes` directly.

Starlette deprecation warning (`httpx` → `httpx2` for TestClient) is non-breaking; tests pass without issue.

The realtime subscription in `_listen()` uses `asyncio.Event().wait()` to hold the task open indefinitely; it is cancelled cleanly on app shutdown via the lifespan teardown.

## Plan Change Log

## Review Triage Log

**Pass 1 — quick lens** | high: 0 | medium: 2 | low: 0 | false: 1 | maybe-false: 0

- `app/routers/sessions.py:84` — `canvas = canvases[0]` unguarded | **medium / patch** | Workspace with no canvas (partial insert failure) raises IndexError → unhandled 500. Confirmed: no prior guard between canvases fetch and index. Patched: raise HTTPException 500 when canvases is empty.
- `supabase/migrations/001_init.sql:6` — orphaned `session_id` column | **medium / patch** | `workspace["id"]` (PK) is used as `session_id` in both route handlers; the `session_id UUID` column is never read or inserted explicitly. Confirmed: zero reads of `workspace["session_id"]` in application code. Patched: column removed from migration.
- `app/routers/sessions.py` (get_session) — AC2 `canvas_id` nesting | **false** | Reviewer's own words: "not a broken contract — the data is present and accessible." The AC says "returns `canvas_id`" without specifying top-level; response has it at `canvas.canvas_id` consistent with the plan's `SessionResponse → CanvasState` model. Bad outcome (missing data) does not occur.

## Design Notes

Access uses a separate `access_token` UUID rather than exposing `session_id` directly — keeps the internal DB identifier from appearing in share URLs. Both are UUIDs; `access_token` is the public-facing one.

Supabase Realtime requires `REPLICA IDENTITY FULL` on the table to emit full old/new row data. Without it, UPDATE events emit only PKs. The migration must set this explicitly.

The `supabase_realtime` publication is Supabase's standard mechanism. Adding a table to it via SQL (`ALTER PUBLICATION supabase_realtime ADD TABLE workspaces`) is the programmatic way; Supabase dashboard does the same thing under the hood.

## Verification

**Commands:**
- `uvicorn app.main:app --reload` — expected: server starts, logs "Realtime subscription active on workspaces"
- `curl -s -X POST http://localhost:8000/sessions -H 'Content-Type: application/json' -d '{"project_name":"test"}' | jq .` — expected: 201 JSON with `session_id`, `access_token`, `access_url`
- `curl -s http://localhost:8000/sessions/{access_token} | jq .quadrants | length` — expected: `4`
- `curl -s -X POST http://localhost:8000/sessions -H 'Content-Type: application/json' -d '{"project_name":""}' | jq .status` — expected: `422`
