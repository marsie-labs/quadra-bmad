from contextlib import asynccontextmanager

from fastapi import FastAPI
from nicegui import ui

from app import realtime
from app.routers.cards import router as cards_router
from app.routers.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await realtime.subscribe()
    yield
    for task in realtime._tasks:
        if not task.done():
            task.cancel()


app = FastAPI(title="Quadra", lifespan=lifespan)
app.include_router(sessions_router)
app.include_router(cards_router)

from app import ui as _app_ui  # noqa: E402, F401 — registers @ui.page routes after app is created
from app.config import settings

ui.run_with(app, storage_secret=settings.storage_secret)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
