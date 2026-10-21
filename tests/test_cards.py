import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key")

from app.main import app  # noqa: E402

NOW = datetime.now(timezone.utc).isoformat()
QUAD_ID = str(uuid.uuid4())
CARD_ID = str(uuid.uuid4())

QUADRANT_ROW = {"id": QUAD_ID}

CARD_ROW = {
    "id": CARD_ID,
    "quadrant_id": QUAD_ID,
    "content": "test card",
    "order_index": 0,
    "author_id": "user-1",
    "deleted_at": None,
    "created_at": NOW,
    "updated_at": NOW,
}

DELETED_CARD_ROW = {**CARD_ROW, "deleted_at": NOW}


def _make_mock_client(
    quad_rows=None,
    card_insert_rows=None,
    card_select_rows=None,
    card_update_rows=None,
):
    if quad_rows is None:
        quad_rows = [QUADRANT_ROW]
    if card_insert_rows is None:
        card_insert_rows = [CARD_ROW]
    if card_select_rows is None:
        card_select_rows = [CARD_ROW]
    if card_update_rows is None:
        card_update_rows = [CARD_ROW]

    def table_factory(name):
        tbl = MagicMock()
        if name == "quadrants":
            tbl.select.return_value.eq.return_value.execute = AsyncMock(
                return_value=MagicMock(data=quad_rows)
            )
        elif name == "cards":
            tbl.insert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=card_insert_rows)
            )
            # chain: select().eq().execute() and select().eq().is_().order().execute()
            select_mock = MagicMock()
            eq_mock = MagicMock()
            is_mock = MagicMock()
            order_mock = MagicMock()

            order_mock.execute = AsyncMock(return_value=MagicMock(data=card_select_rows))
            is_mock.order.return_value = order_mock
            eq_mock.execute = AsyncMock(return_value=MagicMock(data=card_select_rows))
            eq_mock.is_ = MagicMock(return_value=is_mock)
            select_mock.eq.return_value = eq_mock
            tbl.select.return_value = select_mock

            update_mock = MagicMock()
            update_mock.eq.return_value.execute = AsyncMock(
                return_value=MagicMock(data=card_update_rows)
            )
            tbl.update.return_value = update_mock
        return tbl

    mock = MagicMock()
    mock.table = MagicMock(side_effect=table_factory)
    return mock


@pytest.fixture()
def http():
    mock_client = _make_mock_client()
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            yield c


# Matrix row 1: create card → 201
def test_create_card_returns_201(http):
    resp = http.post("/cards", json={
        "quadrant_id": QUAD_ID,
        "content": "test card",
        "order_index": 0,
        "author_id": "user-1",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert uuid.UUID(body["id"])
    assert body["quadrant_id"] == QUAD_ID
    assert body["deleted_at"] is None


# Matrix row 1 error: missing quadrant → 404
def test_create_card_unknown_quadrant_returns_404():
    mock_client = _make_mock_client(quad_rows=[])
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.post("/cards", json={"quadrant_id": str(uuid.uuid4()), "content": "x"})
    assert resp.status_code == 404


# Matrix row 2: list active cards → 200 list, deleted cards excluded
def test_list_cards_returns_active_only():
    mock_client = _make_mock_client(card_select_rows=[CARD_ROW, DELETED_CARD_ROW])
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.get(f"/quadrants/{QUAD_ID}/cards")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["deleted_at"] is None


# Matrix row 2 error: unknown quadrant → 404
def test_list_cards_unknown_quadrant_returns_404():
    mock_client = _make_mock_client(quad_rows=[])
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.get(f"/quadrants/{uuid.uuid4()}/cards")
    assert resp.status_code == 404


# Matrix row 3: update content → 200
def test_update_card_content_returns_200(http):
    updated = {**CARD_ROW, "content": "updated"}
    mock_client = _make_mock_client(card_update_rows=[updated])
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.patch(f"/cards/{CARD_ID}", json={"content": "updated"})
    assert resp.status_code == 200


# Matrix row 4: relocate card (PATCH quadrant_id) → 200
def test_relocate_card_returns_200(http):
    new_quad = str(uuid.uuid4())
    relocated = {**CARD_ROW, "quadrant_id": new_quad}
    mock_client = _make_mock_client(card_update_rows=[relocated])
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.patch(f"/cards/{CARD_ID}", json={"quadrant_id": new_quad})
    assert resp.status_code == 200
    assert resp.json()["quadrant_id"] == new_quad


# Matrix row 5: soft delete → 200 with deleted_at set
def test_soft_delete_card_returns_200_with_deleted_at(http):
    deleted = {**CARD_ROW, "deleted_at": NOW}
    mock_client = _make_mock_client(card_update_rows=[deleted])
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.delete(f"/cards/{CARD_ID}")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None


# Matrix row 6: PATCH on soft-deleted card → 404
def test_patch_deleted_card_returns_404():
    mock_client = _make_mock_client(card_select_rows=[DELETED_CARD_ROW])
    with (
        patch("app.routers.cards.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.patch(f"/cards/{CARD_ID}", json={"content": "nope"})
    assert resp.status_code == 404


# Realtime handler survives all payload shapes
def test_realtime_handle_change_does_not_crash():
    from app.realtime import _make_handler
    handler = _make_handler("cards")
    handler({"eventType": "INSERT", "new": {"id": CARD_ID}, "old": {}})
    handler({"eventType": "UPDATE", "new": {"id": CARD_ID}, "old": {"id": CARD_ID}})
    handler({})
