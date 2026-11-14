"""Bearer auth for write (and in 0.1, read) routes. SPEC §6.3."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from multimcp_api.deps import get_app_settings
from multimcp_api.errors import AppError
from multimcp_api.settings import Settings


async def require_ingest_token(
    settings: Annotated[Settings, Depends(get_app_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Reject when INGEST_TOKEN is empty or the Bearer value does not match."""
    if not settings.ingest_token:
        raise AppError(401, "unauthorized", "ingest token is not configured")
    if authorization is None or not authorization.startswith("Bearer "):
        raise AppError(401, "unauthorized", "missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.ingest_token:
        raise AppError(401, "unauthorized", "invalid ingest token")
