"""Build the EventRepository selected by STORAGE_BACKEND."""

from __future__ import annotations

from multimcp_api.repositories.base import EventRepository
from multimcp_api.repositories.memory import MemoryEventRepository
from multimcp_api.repositories.postgres import PostgresEventRepository, create_async_engine
from multimcp_api.settings import Settings


def build_repository(settings: Settings, *, memory: bool = False) -> EventRepository:
    """Return the storage adapter. BigQuery is imported only when selected."""
    if memory:
        return MemoryEventRepository()
    if settings.storage_backend == "bigquery":
        if settings.eval_backend != "inline":
            raise ValueError(
                "STORAGE_BACKEND=bigquery requires EVAL_BACKEND=inline "
                "(eval claim is Postgres-only; see SPEC §7.1)"
            )
        from multimcp_api.repositories.bigquery import (
            BigQueryEventRepository,
        )

        if not settings.bq_project:
            raise ValueError("BQ_PROJECT is required when STORAGE_BACKEND=bigquery")
        return BigQueryEventRepository(
            project=settings.bq_project,
            dataset=settings.bq_dataset or "multimcp",
        )
    engine = create_async_engine(settings.database_url)
    return PostgresEventRepository(engine)
