"""FastAPI entrypoint: `uvicorn app.main:app --reload`.

Every router is registered here already, so feature tracks never edit this file.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    agents,
    budgets,
    dashboard,
    expenses,
    fx,
    houses,
    imports,
    inbox,
    integrations,
    internal,
    subscriptions,
)
from app.config import get_settings
from app.db.session import init_db
from app.services.errors import DomainError

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Kasa API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(NotImplementedError)
    async def _not_implemented(_request: Request, exc: NotImplementedError) -> JSONResponse:
        # Skeleton endpoints whose track has not landed yet.
        log.info("not implemented: %s", exc)
        return JSONResponse(status_code=501, content={"detail": f"not implemented yet ({exc})"})

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {
            "status": "ok",
            "agents_enabled": settings.agents_enabled,
            "llm_provider": settings.llm_provider,
            "auth": "firebase" if settings.firebase_project_id else "dev",
        }

    for module in (
        expenses,
        houses,
        agents,
        budgets,
        subscriptions,
        dashboard,
        fx,
        integrations,
        inbox,
        imports,
        internal,
    ):
        app.include_router(module.router)
    return app


app = create_app()
