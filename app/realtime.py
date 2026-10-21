import asyncio
import logging

from app.database import get_client

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []


def _make_handler(table: str):
    def _handle_change(payload: dict) -> None:
        event = payload.get("eventType") or payload.get("type", "unknown")
        row_id = (payload.get("new") or {}).get("id", "—")
        logger.info("Realtime %s change: event=%s id=%s", table, event, row_id)
    return _handle_change


async def _listen(table: str) -> None:
    client = await get_client()
    channel = client.channel(f"{table}-realtime")
    channel.on_postgres_changes(
        event="*",
        schema="public",
        table=table,
        callback=_make_handler(table),
    )
    await channel.subscribe()
    logger.info("Realtime subscription active on %s", table)
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        await channel.unsubscribe()
        raise


def _error_callback(t: asyncio.Task) -> None:
    if not t.cancelled() and t.exception():
        logger.error("Realtime task exited: %s", t.exception())


async def subscribe() -> None:
    global _tasks
    for table in ("workspaces", "cards"):
        task = asyncio.create_task(_listen(table))
        task.add_done_callback(_error_callback)
        _tasks.append(task)
