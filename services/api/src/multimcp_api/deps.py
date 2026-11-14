"""FastAPI dependencies that read process state from the app."""

from __future__ import annotations

from fastapi import Request

from multimcp_api.health import HealthProbe
from multimcp_api.settings import Settings


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_health_probe(request: Request) -> HealthProbe:
    return request.app.state.health_probe
