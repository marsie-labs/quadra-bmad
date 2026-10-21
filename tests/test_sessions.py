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
WS_ID = str(uuid.uuid4())
SESSION_ID = str(uuid.uuid4())
ACCESS_TOKEN = str(uuid.uuid4())
CANVAS_ID = str(uuid.uuid4())
QUAD_IDS = [str(uuid.uuid4()) for _ in range(4)]

WORKSPACE_ROW = {
    "id": WS_ID,
    "session_id": SESSION_ID,
    "access_token": ACCESS_TOKEN,
    "project_name": "TestProject",
    "created_at": NOW,
}
CANVAS_ROW = {
    "id": CANVAS_ID,
    "workspace_id": WS_ID,
    "is_active": True,
    "created_at": NOW,
}
QUADRANT_ROWS = [
    {"id": QUAD_IDS[i], "canvas_id": CANVAS_ID, "type": qt, "created_at": NOW}
    for i, qt in enumerate(["IS", "IS_NOT", "DOES", "DOES_NOT"])
]


def _make_mock_client(workspace_rows=None):
    if workspace_rows is None:
        workspace_rows = [WORKSPACE_ROW]

    def table_factory(name):
        tbl = MagicMock()
        if name == "workspaces":
            tbl.insert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=[WORKSPACE_ROW])
            )
            tbl.select.return_value.eq.return_value.execute = AsyncMock(
                return_value=MagicMock(data=workspace_rows)
            )
        elif name == "canvases":
            tbl.insert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=[CANVAS_ROW])
            )
            tbl.select.return_value.eq.return_value.execute = AsyncMock(
                return_value=MagicMock(data=[CANVAS_ROW])
            )
        else:  # quadrants
            tbl.insert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=QUADRANT_ROWS)
            )
            tbl.select.return_value.eq.return_value.execute = AsyncMock(
                return_value=MagicMock(data=QUADRANT_ROWS)
            )
        return tbl

    mock = MagicMock()
    mock.table = MagicMock(side_effect=table_factory)
    return mock


@pytest.fixture()
def http():
    mock_client = _make_mock_client()
    with (
        patch("app.routers.sessions.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            yield c


# Matrix row 1: create session → 201 with workspace + canvas + 4 quadrants
def test_create_session_returns_201_with_full_canvas(http):
    resp = http.post("/sessions", json={"project_name": "TestProject"})
    assert resp.status_code == 201
    body = resp.json()
    assert uuid.UUID(body["session_id"])
    assert uuid.UUID(body["access_token"])
    assert "/board/" in body["access_url"]
    assert len(body["canvas"]["quadrants"]) == 4
    types = {q["type"] for q in body["canvas"]["quadrants"]}
    assert types == {"IS", "IS_NOT", "DOES", "DOES_NOT"}


# Matrix row 2 (happy path): access via link → 200 with full state
def test_get_session_returns_200_with_canvas(http):
    resp = http.get(f"/sessions/{ACCESS_TOKEN}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_name"] == "TestProject"
    assert len(body["canvas"]["quadrants"]) == 4


# Matrix row 2 (error handling): unknown token → 404
def test_get_session_unknown_token_returns_404():
    mock_client = _make_mock_client(workspace_rows=[])
    with (
        patch("app.routers.sessions.get_client", AsyncMock(return_value=mock_client)),
        patch("app.realtime.subscribe", new_callable=AsyncMock),
    ):
        with TestClient(app) as c:
            resp = c.get(f"/sessions/{uuid.uuid4()}")
    assert resp.status_code == 404


# Matrix row 3: realtime callback handles all payload shapes without raising
def test_realtime_handle_change_does_not_crash():
    from app.realtime import _make_handler

    handler = _make_handler("workspaces")
    handler({"eventType": "INSERT", "new": {"id": WS_ID}, "old": {}})
    handler({"eventType": "UPDATE", "new": {"id": WS_ID}, "old": {"id": WS_ID}})
    handler({})


# Matrix row 4: duplicate project name creates a new session (no error)
def test_duplicate_name_allowed(http):
    r1 = http.post("/sessions", json={"project_name": "Dup"})
    r2 = http.post("/sessions", json={"project_name": "Dup"})
    assert r1.status_code == 201
    assert r2.status_code == 201


# Matrix row 5: blank project_name → 422
def test_blank_name_returns_422(http):
    resp = http.post("/sessions", json={"project_name": ""})
    assert resp.status_code == 422
