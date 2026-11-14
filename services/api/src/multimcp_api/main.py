"""ASGI entrypoint for multimcp-api."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from multimcp_api.api.v1 import api_v1_router
from multimcp_api.errors import install_exception_handlers
from multimcp_api.health import AlwaysOkProbe, HealthProbe
from multimcp_api.settings import Settings, get_settings


def create_app(
    *,
    settings: Settings | None = None,
    health_probe: HealthProbe | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(title="multimcp-api", version="0.1.0")
    app.state.settings = resolved
    app.state.health_probe = health_probe or AlwaysOkProbe()
    install_exception_handlers(app)
    app.include_router(api_v1_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("multimcp_api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
