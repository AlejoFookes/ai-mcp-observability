"""FastAPI dependencies that read process state from the app."""

from __future__ import annotations

from fastapi import Request

from multimcp_api.errors import AppError
from multimcp_api.health import HealthProbe
from multimcp_api.repositories.base import EventRepository
from multimcp_api.schemas.ingest import MAX_BODY_BYTES
from multimcp_api.settings import Settings


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_health_probe(request: Request) -> HealthProbe:
    return request.app.state.health_probe


def get_repository(request: Request) -> EventRepository:
    return request.app.state.repository


async def enforce_ingest_body_limit(request: Request) -> None:
    """Reject ingest bodies larger than 1 MiB (SPEC §6.3)."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                raise AppError(413, "payload_too_large", "body exceeds 1 MiB")
        except ValueError:
            raise AppError(422, "validation_error", "invalid Content-Length") from None
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise AppError(413, "payload_too_large", "body exceeds 1 MiB")
