"""FastAPI application factory.

Run with:  python run.py   or   uvicorn app.main:app
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app import database
from app.api import analysis, dashboard, datasets, monitoring, reports
from app.config import APP_NAME, APP_VERSION, ConfigError, Settings, get_settings
from app.utils.validators import AppError

log = logging.getLogger("aidq")

DESCRIPTION = """
One unified data-quality platform: upload a dataset, click **Analyze**, and the backend runs the complete
pipeline (profiling, quality score, statistical + ML anomaly detection, consensus, explanations,
recommendations, remediation plan, drift, monitoring, alerts, trends, forecast, final decision).
"""


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            database.configure(settings.database_url)
            database.init_db()
            app.state.db_error = None
        except Exception as exc:  # noqa: BLE001 - the app still starts; endpoints return 503
            app.state.db_error = type(exc).__name__
            log.error("Database could not be initialised (%s). Check DATABASE_URL.", type(exc).__name__)
        yield

    app = FastAPI(title=APP_NAME, version=APP_VERSION, description=DESCRIPTION, lifespan=lifespan,
                  docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.db_error = None
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["*"])

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "problem": e["msg"]}
                   for e in exc.errors()]
        return _error(422, "validation_error", "Some inputs are invalid. " +
                      "; ".join(f"{d['field'] or 'request'}: {d['problem']}" for d in details[:3]), details[:10])

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError):
        log.error("Database error: %s", type(exc).__name__)
        return _error(503, "database_unavailable",
                      "The database is currently unavailable. Please check the DATABASE_URL configuration "
                      "and that the database server is running.")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")                      # full trace goes to the server log only
        return _error(500, "internal_error", "Something went wrong on the server. Please try again.")

    for module in (datasets, analysis, monitoring, dashboard, reports):
        app.include_router(module.router)

    frontend = Path(settings.frontend_dir)
    if frontend.exists():
        app.mount("/static", StaticFiles(directory=frontend), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(frontend / "index.html")

    return app


def _build_default_app() -> FastAPI:
    try:
        return create_app()
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc


app = _build_default_app()
