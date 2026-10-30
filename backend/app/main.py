from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import analyses
from .routers import analyses as analyses_router
from .routers import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    analyses.mark_interrupted()
    yield


app = FastAPI(title="SmartKOL API", version="0.1.0", lifespan=lifespan)
app.include_router(settings.router)
app.include_router(analyses_router.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}
