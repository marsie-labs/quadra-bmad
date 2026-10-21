from collections import defaultdict

from nicegui import background_tasks

_subscribers: dict[str, list] = defaultdict(list)


def register(quadrant_id: str, fn) -> None:
    _subscribers[quadrant_id].append(fn)


def unregister(quadrant_id: str, fn) -> None:
    _subscribers[quadrant_id] = [f for f in _subscribers[quadrant_id] if f is not fn]


def notify(quadrant_id: str) -> None:
    for fn in list(_subscribers.get(quadrant_id, [])):
        background_tasks.create(fn())
