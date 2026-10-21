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


if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
