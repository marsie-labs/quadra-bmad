---
title: 'NiceGUI Canvas UI with Realtime Card Sync'
type: 'feature'
ticket: ''
created: '2026-10-21'
status: 'built'
baseline_revision: '71af5e938b8ed04df2bd346df655e935ff37cffb'
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

**Problem:** The backend has full card CRUD and Supabase Realtime, but there is no UI — users cannot view or interact with the four-quadrant canvas in a browser.

**Approach:** Mount a NiceGUI app on the existing FastAPI server exposing a canvas page at `/board/{access_token}`. The page loads the session and cards directly via the shared Supabase client, renders a four-column IS / IS NOT / DOES / DOES NOT grid, supports card create/edit/delete/move with optimistic updates, and refreshes affected quadrant columns in real time when the supabase-py subscription fires a card change event.

## Boundaries & Constraints

**Always:** NiceGUI is mounted on the existing FastAPI app (single process, `ui.run_with(app)`); card mutations go directly to Supabase via `get_client()` — no self-HTTP calls; `access_url` in `POST /sessions` response changes to `/board/{access_token}` (the human-facing share link); `author_id` is a per-browser UUID persisted in `app.storage.user`; optimistic updates must be reverted on failure with a `ui.notify` error.

**Never:** No page-level authentication; no drag-and-drop between quadrants (move uses a select dialog); no server-sent events or polling loops; no changes to the JSON REST API surface.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Load canvas | Browser opens `/board/{access_token}` | Page renders with 4 quadrant columns; cards loaded per quadrant ordered by `order_index` | Redirect to `/` with error message if token unknown |
| Add card | User types text and clicks Add in a quadrant | Card appears immediately in that column; `POST /cards` fires in background | On failure: card removed, `ui.notify` error shown |
| Edit card | User clicks edit, changes text, confirms | Card text updates immediately; `PATCH /cards/{id}` fires | On failure: text reverted, `ui.notify` error |
| Delete card | User clicks delete on a card | Card disappears immediately; `DELETE /cards/{id}` fires | On failure: card re-added, `ui.notify` error |
| Move card | User opens card menu, selects target quadrant | Card moves to new column immediately; `PATCH /cards/{id}` with new `quadrant_id` | On failure: card returns to original column, `ui.notify` error |
| Realtime update | Another client mutates a card | Affected quadrant column refreshes silently without user interaction | Supabase handles delivery; UI just re-queries on event |

</frozen-after-approval>

## Code Map

Existing files to modify:

- `pyproject.toml` — add `nicegui>=2.0.0` to runtime deps
- `app/config.py` — add `storage_secret: str = "change-me-in-env"` for NiceGUI session storage
- `app/routers/sessions.py:44-45` — change `access_url` path from `/sessions/` to `/board/`
- `app/realtime.py:11-16` — extend `_make_handler("cards")` to call `realtime_ui.notify(quadrant_id)` from card change payload
- `app/main.py` — add `import app.ui` (registers `@ui.page` routes); call `ui.run_with(app, storage_secret=settings.storage_secret)` before the `__main__` block

New files:

- `app/ui/__init__.py` — imports `app.ui.canvas` to register the `@ui.page` decorator at import time
- `app/ui/canvas.py` — `@ui.page('/board/{access_token}')` handler: loads session + cards, renders 2×2 quad grid, card add/edit/delete/move with optimistic state, registers quadrant refresh callbacks with `realtime_ui`
- `app/ui/realtime_ui.py` — per-quadrant subscriber registry: `register(quadrant_id, refresh_fn)`, `unregister(quadrant_id, refresh_fn)`, `notify(quadrant_id)` schedules `refresh_fn()` for every registered client via `background_tasks.create`
- `tests/test_realtime_ui.py` — unit tests for the subscriber registry (register, unregister, notify, notify on unknown quadrant)

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml` — Add `nicegui>=2.0.0` to runtime dependencies
- [ ] `app/config.py` — Add `storage_secret: str = "change-me-in-env"` field
- [ ] `app/ui/__init__.py` — Create package; import `app.ui.canvas` to trigger route registration
- [ ] `app/ui/realtime_ui.py` — Implement subscriber registry with `register`, `unregister`, `notify`
- [ ] `app/ui/canvas.py` — Implement NiceGUI canvas page with all card operations and realtime refresh registration
- [ ] `app/realtime.py` — Extend cards `_make_handler` to call `realtime_ui.notify(quadrant_id)` using card payload's `quadrant_id`
- [ ] `app/main.py` — Import `app.ui`; call `ui.run_with(app, storage_secret=settings.storage_secret)`
- [ ] `app/routers/sessions.py` — Change `access_url` construction to use `/board/` prefix
- [ ] `tests/test_realtime_ui.py` — Tests for registry: register, unregister removes only target, notify calls registered fn, notify on unknown quadrant does not raise

**Acceptance Criteria:**
- Given a valid `access_token`, when `/board/{access_token}` is opened, then the page renders four columns labelled IS, IS NOT, DOES, DOES NOT, each containing the quadrant's active cards.
- Given an unknown `access_token`, when `/board/{access_token}` is opened, then the user sees an error message (not a 500 page).
- Given a loaded canvas, when a user adds text and clicks Add in a quadrant, then the card appears in that column before the Supabase write completes (optimistic), and is removed with a `ui.notify` error if the write fails.
- Given a loaded canvas, when a user deletes a card, then the card disappears immediately and is restored with a `ui.notify` error if `DELETE /cards/{id}` fails.
- Given a loaded canvas, when a user moves a card to another quadrant, then the card appears in the target column immediately and reverts on failure.
- Given two browser tabs open on the same canvas, when one tab creates a card, then the other tab's affected quadrant column refreshes without a page reload.
- Given `realtime_ui.notify(quadrant_id)` is called, when callbacks are registered for that quadrant, then each registered callback is scheduled via `background_tasks.create`.

## Implementation Notes

## Plan Change Log

## Review Triage Log

**Pass 1 — quick lens** | high: 1 | medium: 0 | low: 1 | false: 0 | maybe-false: 0

- `app/ui/canvas.py:129` — `ui.timer(0, lambda r=refresh: r(), once=True)` sync lambda discards coroutine | **high / patch** | NiceGUI checks `asyncio.iscoroutinefunction`; the lambda fails that check so the coroutine returned by `refresh()` is never awaited. Cards never load on initial render. AC1 unmet. Fix: `ui.timer(0, refresh, once=True)`.
- `app/ui/canvas.py:120-123` — missing `await refresh()` after `placeholder.delete()` on insert failure | **low / patch** | If a realtime event fires between the placeholder being added and the insert failure, the ghost placeholder persists until the next refresh. Fix is direct: add `await refresh()` after `placeholder.delete()`.

## Design Notes

`app.ui` must be imported in `app/main.py` AFTER the FastAPI `app` object is created but BEFORE `ui.run_with(app, ...)` is called — otherwise `@ui.page` decorators fire against the wrong app instance. The import order in `main.py` is: create `app`, include routers, import `app.ui`, call `ui.run_with`.

`realtime_ui.notify` receives a `quadrant_id` extracted from the Supabase card change payload (`payload["new"]["quadrant_id"]` for INSERT/UPDATE; `payload["old"]["quadrant_id"]` for DELETE). The handler must handle both `new` and `old` keys to cover all event types.

`access_url` change (`/sessions/` → `/board/`) is intentional: the original URL returned the JSON API, not a page. Existing `GET /sessions/{access_token}` JSON endpoint is unchanged.

`ui.run_with(app, storage_secret=...)` does not start a server — it configures the FastAPI app in-place. `python -m app.main` continues to start uvicorn as before.

## Verification

**Commands:**
- `uv run pytest tests/test_realtime_ui.py -v` — expected: all tests pass
- `uv run pytest tests/ -v` — expected: all 15+ tests pass (no regressions)
- `python -m app.main` then open `http://localhost:8001/board/<token>` — expected: canvas page loads with 4 quadrant columns
