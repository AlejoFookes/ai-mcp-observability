"""Shared query-window validation (SPEC §6.3: max 31 days, from inclusive, to exclusive)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from multimcp_api.errors import AppError

MAX_WINDOW = timedelta(days=31)


def validate_window(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None:
        raise AppError(
            422,
            "validation_error",
            "from and to must be timezone-aware ISO-8601 timestamps",
        )
    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    if end_utc <= start_utc:
        raise AppError(422, "validation_error", "to must be after from")
    if end_utc - start_utc > MAX_WINDOW:
        raise AppError(422, "validation_error", "query window exceeds 31 days")
