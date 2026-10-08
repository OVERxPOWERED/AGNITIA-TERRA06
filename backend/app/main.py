"""FastAPI application factory. Run: uvicorn app.main:app --reload --port 8000 (from backend/)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import alerts, assumptions, dispatch, dsm, forecast, health, impact, models, whatif
from app.db.models import engine
from app.scheduler import ForecastJob, attach_loop
from app.services.runs import NoRunYet
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine()                                   # create SQLite tables
    from app.services import runs
    try:
        runs.latest()                          # warm caches
    except NoRunYet:
        pass
    app.state.subscribers = set()
    attach_loop(app)
    job = ForecastJob(app)
    if get_settings().scheduler_enabled:
        job.start()
    app.state.job = job
    yield
    if get_settings().scheduler_enabled:
        job.stop()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="TERRA API", version=s.version, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_methods=["*"], allow_headers=["*"])
    for r in (health, forecast, models, alerts, dispatch, whatif, dsm, impact, assumptions):
        app.include_router(r.router)

    @app.exception_handler(NoRunYet)
    async def no_run(_: Request, exc: NoRunYet):
        return JSONResponse(status_code=503, content={"error": {"code": "NO_DATA_YET", "message": str(exc)}})

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL", "message": str(exc)}})

    return app


app = create_app()
