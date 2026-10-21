from unittest.mock import AsyncMock, patch

import app.ui.realtime_ui as rui


def setup_function():
    rui._subscribers.clear()


def teardown_function():
    rui._subscribers.clear()


def test_register_adds_fn():
    fn = AsyncMock()
    rui.register("q1", fn)
    assert fn in rui._subscribers["q1"]


def test_unregister_removes_only_target():
    fn1, fn2 = AsyncMock(), AsyncMock()
    rui.register("q1", fn1)
    rui.register("q1", fn2)
    rui.unregister("q1", fn1)
    assert fn1 not in rui._subscribers["q1"]
    assert fn2 in rui._subscribers["q1"]


def test_unregister_noop_when_not_registered():
    fn = AsyncMock()
    rui.unregister("q1", fn)  # should not raise


def test_notify_schedules_registered_fn():
    fn = AsyncMock()
    rui.register("q1", fn)
    with patch("app.ui.realtime_ui.background_tasks") as mock_bt:
        rui.notify("q1")
        assert mock_bt.create.call_count == 1


def test_notify_schedules_all_registered_fns():
    fn1, fn2 = AsyncMock(), AsyncMock()
    rui.register("q1", fn1)
    rui.register("q1", fn2)
    with patch("app.ui.realtime_ui.background_tasks") as mock_bt:
        rui.notify("q1")
        assert mock_bt.create.call_count == 2


def test_notify_unknown_quadrant_does_not_raise():
    rui.notify("no-such-quadrant-id")


def test_notify_after_unregister_does_not_call_fn():
    fn = AsyncMock()
    rui.register("q1", fn)
    rui.unregister("q1", fn)
    with patch("app.ui.realtime_ui.background_tasks") as mock_bt:
        rui.notify("q1")
        mock_bt.create.assert_not_called()
