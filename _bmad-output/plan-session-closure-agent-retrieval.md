---
title: 'Session Closure and Agent Retrieval'
type: 'feature'
ticket: ''
created: '2026-10-21'
status: 'built'
baseline_revision: 'eabf8f7ba43a3c716ae663296a84ac3f141a62db'
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

**Problem:** Once participants finish a session there is no way to lock the canvas, and the external agent harness has no way to pull the structured results — it would receive live, possibly incomplete data with no signal that the session is done.

**Approach:** Add a `status` column (`open` | `closed`) to `workspaces`. Expose a close endpoint (`POST /sessions/{session_id}/close`) that sets the status and a results endpoint (`GET /sessions/{session_id}/results`) that returns the full card dataset only when closed (409 if still open). Add a "Close Session" button to the NiceGUI canvas that confirms, closes via the endpoint, and re-renders the canvas read-only.

## Boundaries & Constraints

**Always:** `session_id` in both new endpoints is the workspace `id` UUID (the value already returned as `session_id` in `SessionResponse`); all existing REST endpoints remain unchanged; read-only mode disables Add, Edit, Delete, and Move for every quadrant; `GET /sessions/{session_id}/results` returns only active (non-deleted) cards; closure is permanent — no reopen endpoint.

**Never:** No authentication on close or results; no `closed_at` timestamp column (out of scope); no drag-and-drop changes; no changes to the Supabase Realtime subscription.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Close open session | `POST /sessions/{id}/close`, workspace `status=open` | 200 — workspace row with `status=closed` | 404 if workspace not found |
| Close already-closed session | `POST /sessions/{id}/close`, workspace `status=closed` | 409 — "Session is already closed" | — |
| Get results — closed | `GET /sessions/{id}/results`, `status=closed` | 200 — `SessionResultsOut` with all quadrants and active cards | 404 if workspace not found |
| Get results — open | `GET /sessions/{id}/results`, `status=open` | 409 — "Session is still open" | — |
| Canvas loads closed | Browser opens `/board/{token}`, `status=closed` | Page renders read-only: no Add/Edit/Delete/Move; "Session closed" banner shown | — |
| Canvas loads open | Browser opens `/board/{token}`, `status=open` | Page renders normally with Close Session button visible | — |
| User clicks Close Session | Confirmation dialog, user confirms | Close endpoint called; canvas re-renders read-only | On failure: `ui.notify` error, canvas stays editable |

</frozen-after-approval>

## Code Map

Existing files to modify:

- `supabase/migrations/001_init.sql` — defines `workspaces`; `003_workspace_status.sql` adds to it
- `app/models.py` — add `QuadrantResults`, `SessionResultsOut`; add `status: str` field to `SessionResponse`
- `app/routers/sessions.py` — add `POST /sessions/{session_id}/close` and `GET /sessions/{session_id}/results`; update both existing endpoints to return `status` field (already in workspace row, just needs inclusion in `SessionResponse`)
- `app/ui/canvas.py:30-76` — `canvas_page` loads workspace; pass `status` to `_build_quadrant_column`; add "Close Session" button and banner to header area
- `app/ui/canvas.py:78-138` — `_build_quadrant_column` receives `is_closed: bool`; gates add input + button; `_render_card` receives `is_closed: bool`; gates edit/delete/move buttons
- `tests/test_sessions.py` — add 5 tests covering the I/O matrix rows for close and results

New file:

- `supabase/migrations/003_workspace_status.sql` — `ALTER TABLE workspaces ADD COLUMN status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed'))`

## Tasks & Acceptance

**Execution:**
- [ ] `supabase/migrations/003_workspace_status.sql` — Add `status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed'))` column to workspaces
- [ ] `app/models.py` — Add `status: str` to `SessionResponse`; add `QuadrantResults(id, type, cards)` and `SessionResultsOut(session_id, project_name, status, canvas_id, quadrants)` models
- [ ] `app/routers/sessions.py` — Add `POST /sessions/{session_id}/close` (404 if missing, 409 if already closed, 200 on success); add `GET /sessions/{session_id}/results` (404 if missing, 409 if open, 200 with `SessionResultsOut`); include `status` field in both existing endpoints' `SessionResponse` returns
- [ ] `app/ui/canvas.py` — In `canvas_page`: detect `workspace["status"]`; pass `is_closed` to `_build_quadrant_column`; add "Session closed" banner when closed; add "Close Session" button in header when open (confirmation dialog, calls close endpoint, re-renders on success). In `_build_quadrant_column`: when `is_closed=True` skip add input and button. In `_render_card`: when `is_closed=True` skip edit/delete/move buttons.
- [ ] `tests/test_sessions.py` — Add tests: close open session returns 200 with status=closed; close unknown session returns 404; close already-closed session returns 409; results on closed session returns 200 with quadrant structure; results on open session returns 409

**Acceptance Criteria:**
- Given an open workspace, when `POST /sessions/{session_id}/close` is called, then HTTP 200 is returned and the workspace `status` is `closed`.
- Given a closed workspace, when `POST /sessions/{session_id}/close` is called again, then HTTP 409 is returned.
- Given a closed workspace, when `GET /sessions/{session_id}/results` is called, then HTTP 200 returns a `SessionResultsOut` containing all quadrants each with their active cards.
- Given an open workspace, when `GET /sessions/{session_id}/results` is called, then HTTP 409 is returned with detail "Session is still open".
- Given a canvas with `status=open`, when the page loads, then a "Close Session" button is visible and cards are editable.
- Given a canvas with `status=closed`, when the page loads, then a "Session closed" banner is shown, the Add input and button are absent, and Edit/Delete/Move buttons are absent on all cards.
- Given an open canvas, when the user confirms Close Session, then the canvas re-renders read-only without a page reload.

## Implementation Notes

## Plan Change Log

## Review Triage Log

**Pass 1 — quick lens** | high: 0 | medium: 1 | low: 3 | false: 3 | maybe-false: 0

- `app/routers/sessions.py:65,146` — route shadowing concern (GET /{access_token} vs GET /{id}/results) | **false** | Two-segment paths don't conflict with one-segment wildcard; reviewer self-retracted.
- `app/ui/canvas.py:confirm_close` — bypasses REST 409 guard by calling DB directly | **false** | Plan explicitly says "no self-HTTP calls"; direct DB is intentional; 409 guards the REST layer; double-update is idempotent (closed → closed harmless).
- `app/ui/canvas.py:confirm_close` — missing optimistic hide of Close Session button before DB call | **low / patch** | Design Notes state this as expected; button remains visible between dlg.close() and ui.navigate.reload(). Fixed: `_btn_ref` list captures button for hide/restore.
- `app/routers/sessions.py:close_session` — returns `dict` not typed response model | **low / reject** | Fix would add a `WorkspaceOut` model (new public surface not in plan); runtime correct.
- `tests/test_sessions.py` — missing `test_get_results_unknown_session_returns_404` | **medium / patch** | I/O matrix error column says "404 if workspace not found"; `_make_results_mock(found=False)` existed unused. Added test.
- `tests/test_sessions.py:test_get_results_closed_session_returns_200` — no assertion on session_id/canvas_id | **low / reject** | Pydantic validates model shape on deserialization; additional field assertions add noise not coverage.
- `app/ui/canvas.py` — Realtime registered even when closed | **false / not a finding** | Plan says no Realtime changes; read-only state is preserved through refresh callbacks.
- `supabase/migrations/003_workspace_status.sql` — missing trailing newline | **low / reject** | Cosmetic POSIX convention; migration executes fine.
- `app/models.py:SessionResponse,SessionResultsOut` — `status: str` not `Literal["open", "closed"]` | **low / patch** | Direct fix; mirrors DB CHECK constraint. Applied.

## Design Notes

`POST /sessions/{session_id}/close` uses the workspace `id` (not `access_token`) because the agent harness holds `session_id` from the `POST /sessions` response — that is the `id` field. The NiceGUI canvas already has the workspace row in scope, so it reads `workspace["id"]` to call the endpoint.

The close button calls `POST /sessions/{session_id}/close` via `get_client()` directly (same pattern as card mutations) — no self-HTTP calls.

After a successful close from the UI, the simplest re-render is `ui.navigate.reload()` — this re-runs `canvas_page` which will now see `status=closed` and render read-only. An optimistic hide of the close button before the call improves perceived responsiveness.

`_render_card` already receives `refresh_fn` as a parameter; adding `is_closed: bool` follows the same pattern.

## Verification

**Commands:**
- `uv run pytest tests/test_sessions.py -v` — expected: all tests pass including 5 new ones
- `uv run pytest tests/ -v` — expected: all tests pass (no regressions)
- `SUPABASE_ACCESS_TOKEN=<token> supabase db push` — expected: migration 003 applied

**Manual checks:**
- Open `/board/{token}` for an open session: Close Session button visible, cards editable
- Click Close Session, confirm: page re-renders with "Session closed" banner, no Add/Edit/Delete/Move controls
- `GET /sessions/{session_id}/results` returns full quadrant+card structure
- `GET /sessions/{session_id}/results` on open session returns 409
