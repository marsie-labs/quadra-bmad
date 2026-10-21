from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import realtime
from app.routers.sessions import router as sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await realtime.subscribe()
    yield
    if realtime._task and not realtime._task.done():
        realtime._task.cancel()


app = FastAPI(title="Quadra", lifespan=lifespan)
app.include_router(sessions_router)
