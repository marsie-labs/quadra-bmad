---
title: 'Realtime Card CRUD API'
type: 'feature'
ticket: ''
created: '2026-10-21'
status: 'built'
baseline_revision: '7b07dff268ba9ef3f6099b9793d28f7b6545ca51'
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

**Problem:** The canvas has quadrants but no cards — participants cannot add, edit, move, or remove content within the IS / IS NOT / DOES / DOES NOT quadrants, and no realtime broadcast exists for card mutations.

**Approach:** Add a `cards` table (FK to `quadrants`), four REST endpoints for card lifecycle (create, update, soft-delete, relocate), and a server-side supabase-py realtime subscription on the cards table so connected clients receive instant broadcast of all card mutations.

## Boundaries & Constraints

**Always:** Cards are soft-deleted (set `deleted_at`), never hard-deleted; `GET /quadrants/{id}/cards` excludes soft-deleted rows; the `cards` table must have Realtime enabled; relocate is handled by PATCH (update `quadrant_id`), not a separate verb; card content may be empty string.

**Never:** No user authentication; no hard deletes; no card ordering enforcement server-side (client owns `order_index`); NiceGUI UI is out of scope for this plan (deferred).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Create card | `POST /cards` `{quadrant_id, content, author_id, order_index}` | 201 — card row; Realtime INSERT broadcast | 422 if `quadrant_id` missing; 404 if quadrant not found |
| List cards | `GET /quadrants/{quadrant_id}/cards` | 200 — active cards ordered by `order_index` | 404 if quadrant not found |
| Update content | `PATCH /cards/{id}` `{content: "new text"}` | 200 — updated card row; Realtime UPDATE broadcast | 404 if card not found or already deleted |
| Relocate card | `PATCH /cards/{id}` `{quadrant_id: <other_uuid>}` | 200 — card with new `quadrant_id`; Realtime UPDATE | 404 if target quadrant not found |
| Soft delete | `DELETE /cards/{id}` | 200 — card with `deleted_at` set; Realtime UPDATE broadcast | 404 if card not found or already deleted |
| Mutate deleted card | `PATCH /cards/{id}` where `deleted_at IS NOT NULL` | 404 — card treated as gone | — |

</frozen-after-approval>

## Code Map

Existing files relevant to this change:

- `supabase/migrations/001_init.sql` — existing schema; `quadrants.id` is the FK target for `cards.quadrant_id`
- `app/models.py` — add `CardCreate`, `CardUpdate`, `CardOut` here; `QuadrantType` already defined
- `app/realtime.py` — extend to subscribe to `cards` table with a second channel; `_task` becomes a list of two tasks
- `app/main.py` — include `cards_router` alongside existing `sessions_router`
- `app/database.py` — `get_client()` reused as-is
- `app/routers/sessions.py` — no changes; reference only for router pattern

New files:

- `supabase/migrations/002_cards.sql` — `cards` DDL; `REPLICA IDENTITY FULL`; add to `supabase_realtime` publication
- `app/routers/cards.py` — four endpoints: POST /cards, GET /quadrants/{id}/cards, PATCH /cards/{id}, DELETE /cards/{id}

## Tasks & Acceptance

**Execution:**
- [ ] `supabase/migrations/002_cards.sql` — Create `cards` table (id, quadrant_id FK, content, order_index, author_id, deleted_at, created_at, updated_at); REPLICA IDENTITY FULL; add to supabase_realtime publication
- [ ] `app/models.py` — Add `CardCreate` (quadrant_id, content, author_id, order_index), `CardUpdate` (all optional: content, quadrant_id, order_index), `CardOut` (all columns including deleted_at)
- [ ] `app/routers/cards.py` — Implement POST /cards, GET /quadrants/{quadrant_id}/cards, PATCH /cards/{card_id}, DELETE /cards/{card_id}; 404 on missing/deleted where required
- [ ] `app/realtime.py` — Add second channel `"cards-realtime"` subscribing to `cards` table; `_task` → `_tasks: list`; `subscribe()` creates both tasks; shutdown cancels all
- [ ] `app/main.py` — Import and include `cards_router`
- [ ] `tests/test_cards.py` — Tests covering all six I/O Matrix rows

**Acceptance Criteria:**
- Given a valid `quadrant_id`, when `POST /cards` is called, then a card row is created with the provided metadata and HTTP 201 is returned.
- Given a `quadrant_id` with existing active cards, when `GET /quadrants/{quadrant_id}/cards` is called, then HTTP 200 returns only rows where `deleted_at IS NULL`, ordered by `order_index`.
- Given an existing active card, when `PATCH /cards/{id}` is called with `{content: "x"}`, then the card's content is updated and HTTP 200 is returned.
- Given an existing active card, when `PATCH /cards/{id}` is called with a different `quadrant_id`, then the card's `quadrant_id` is updated (relocate) and HTTP 200 is returned.
- Given an existing active card, when `DELETE /cards/{id}` is called, then `deleted_at` is set (not NULL) and HTTP 200 is returned.
- Given a soft-deleted card, when `PATCH /cards/{id}` is called, then HTTP 404 is returned.
- Given the server starts, when a card INSERT or UPDATE occurs, then the server-side cards realtime handler logs the event without crashing.

## Implementation Notes

## Plan Change Log

## Review Triage Log

**Pass 1 — quick lens** | high: 0 | medium: 2 | low: 0 | false: 0 | maybe-false: 1 (rejected)

- `app/routers/cards.py:99,122` — unguarded `.data[0]` after UPDATE in `update_card` and `delete_card` | **medium / patch** | Same class as sessions canvas bug: concurrent delete between SELECT and UPDATE returns empty `.data`, raising IndexError → 500. Confirmed at both lines. Fix: guard with `if not card_data: raise HTTPException(500, ...)`.
- `tests/test_cards.py:122-126` — `test_list_cards_returns_active_only` doesn't assert deleted cards are excluded | **medium / patch** | Mock always returns non-deleted `CARD_ROW`; `.is_("deleted_at","null")` filter is never exercised by the test. AC2 states "only rows where deleted_at IS NULL". Fix: add app-level filter in router + update test mock to include a deleted card and assert it's absent.
- `app/realtime.py:8` — `_tasks` list accumulates across reload cycles | **maybe-false / low if true → rejected** | uvicorn `--reload` restarts the worker process, re-executing `_tasks: list = []`; accumulation requires in-process module reload without module re-execution. Low severity even if true. Rejected per rule.

## Design Notes

`PATCH /cards/{id}` handles both content updates and quadrant relocations — the client sends only the fields it wants to change. This avoids a separate `PUT /cards/{id}/move` verb while keeping the contract simple.

`updated_at` must be set on every PATCH. Supabase does not auto-update it; the router must pass `updated_at: NOW()` (as an ISO string) in the update payload.

The existing `_task: asyncio.Task | None` in `app/realtime.py` becomes `_tasks: list[asyncio.Task]` to hold both the workspaces and cards subscription tasks. The shutdown loop in `app/main.py`'s lifespan must cancel all tasks in the list.

## Verification

**Commands:**
- `uv run pytest tests/test_cards.py -v` — expected: all tests pass
- `curl -s -X POST http://localhost:8001/cards -H 'Content-Type: application/json' -d '{"quadrant_id":"<uuid>","content":"test","order_index":0}' | jq .` — expected: 201 with card id
- `curl -s http://localhost:8001/quadrants/<uuid>/cards | jq length` — expected: count of active cards
- `curl -s -X DELETE http://localhost:8001/cards/<id> | jq .deleted_at` — expected: non-null timestamp
