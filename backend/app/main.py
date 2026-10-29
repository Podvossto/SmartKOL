from fastapi import FastAPI

from .routers import settings

app = FastAPI(title="SmartKOL API", version="0.1.0")
app.include_router(settings.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}
