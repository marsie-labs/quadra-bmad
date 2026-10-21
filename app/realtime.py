import asyncio
import logging

from app.database import get_client

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


def _handle_change(payload: dict) -> None:
    event = payload.get("eventType") or payload.get("type", "unknown")
    row_id = (payload.get("new") or {}).get("id", "—")
    logger.info("Realtime workspace change: event=%s id=%s", event, row_id)


async def _listen() -> None:
    client = await get_client()
    channel = client.channel("workspace-realtime")
    channel.on_postgres_changes(
        event="*",
        schema="public",
        table="workspaces",
        callback=_handle_change,
    )
    await channel.subscribe()
    logger.info("Realtime subscription active on workspaces")
    try:
        # Hold the task open until cancelled at shutdown
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        await channel.unsubscribe()
        raise


async def subscribe() -> None:
    global _task
    _task = asyncio.create_task(_listen())
    _task.add_done_callback(
        lambda t: (
            logger.error("Realtime task exited: %s", t.exception())
            if not t.cancelled() and t.exception()
            else None
        )
    )
