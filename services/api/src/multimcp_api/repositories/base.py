"""Storage Protocol. Routers depend on this, not on Postgres or BigQuery."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from multimcp.models import GenAIEvent, McpEvent
from multimcp_api.domain.models import (
    CompareQuery,
    CompareResult,
    EvalJob,
    EvalOutcome,
    FinOpsRow,
    InsertResult,
    LatencyRow,
    TraceSpan,
    WindowQuery,
)


class EventRepository(Protocol):
    async def insert_genai(self, events: Sequence[GenAIEvent]) -> InsertResult: ...

    async def insert_mcp(self, events: Sequence[McpEvent]) -> InsertResult: ...

    async def finops_summary(self, query: WindowQuery) -> list[FinOpsRow]: ...

    async def latency(self, query: WindowQuery) -> list[LatencyRow]: ...

    async def get_trace(self, trace_id: str) -> list[TraceSpan]: ...

    async def compare(self, query: CompareQuery) -> CompareResult: ...

    async def enqueue_eval(self, job: EvalJob) -> None: ...

    async def get_eval(self, job_id: UUID) -> EvalJob | None: ...

    async def start_eval(self, job_id: UUID, lock_seconds: int) -> EvalJob | None: ...

    async def claim_eval_jobs(self, limit: int, lock_seconds: int) -> list[EvalJob]: ...

    async def complete_eval(self, job_id: UUID, outcome: EvalOutcome) -> None: ...

    async def requeue_eval(self, job_id: UUID) -> None: ...

    async def ping(self) -> bool: ...
