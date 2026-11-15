"""In-memory EventRepository for CI and local tests without Postgres."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
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
    TraceSummary,
    WindowQuery,
)
from multimcp_api.repositories import stats


class MemoryEventRepository:
    def __init__(self) -> None:
        self.genai: dict[UUID, GenAIEvent] = {}
        self.mcp: dict[UUID, McpEvent] = {}
        self.evals: dict[UUID, EvalJob] = {}

    async def ping(self) -> bool:
        return True

    async def insert_genai(self, events: Sequence[GenAIEvent]) -> InsertResult:
        accepted = 0
        duplicates = 0
        for event in events:
            if event.event_id in self.genai:
                duplicates += 1
                continue
            self.genai[event.event_id] = event
            accepted += 1
        return InsertResult(accepted=accepted, duplicates=duplicates)

    async def insert_mcp(self, events: Sequence[McpEvent]) -> InsertResult:
        accepted = 0
        duplicates = 0
        for event in events:
            if event.event_id in self.mcp:
                duplicates += 1
                continue
            self.mcp[event.event_id] = event
            accepted += 1
        return InsertResult(accepted=accepted, duplicates=duplicates)

    async def finops_summary(self, query: WindowQuery) -> list[FinOpsRow]:
        if query.group_by == "mcp_server":
            return stats.aggregate_finops_mcp(list(self.mcp.values()), query)
        return stats.aggregate_finops_genai(list(self.genai.values()), query)

    async def latency(self, query: WindowQuery) -> list[LatencyRow]:
        if query.group_by == "mcp_tool":
            return stats.aggregate_latency_mcp(list(self.mcp.values()), query)
        return stats.aggregate_latency_genai(list(self.genai.values()), query)

    async def get_trace(self, trace_id: str) -> list[TraceSpan]:
        return stats.build_trace(list(self.genai.values()), list(self.mcp.values()), trace_id)

    async def list_traces(
        self, *, start: datetime, end: datetime, limit: int
    ) -> list[TraceSummary]:
        return stats.list_trace_summaries(
            list(self.genai.values()),
            list(self.mcp.values()),
            start=start,
            end=end,
            limit=limit,
        )

    async def compare(self, query: CompareQuery) -> CompareResult:
        return stats.build_compare(list(self.genai.values()), query)

    async def enqueue_eval(self, job: EvalJob) -> None:
        stored = job.model_copy(
            update={
                "status": "queued",
                "created_at": job.created_at or datetime.now(UTC),
            }
        )
        self.evals[stored.job_id] = stored

    async def get_eval(self, job_id: UUID) -> EvalJob | None:
        return self.evals.get(job_id)

    async def start_eval(self, job_id: UUID, lock_seconds: int) -> EvalJob | None:
        job = self.evals.get(job_id)
        if job is None:
            return None
        now = datetime.now(UTC)
        updated = job.model_copy(
            update={
                "status": "running",
                "started_at": now,
                "locked_at": now + timedelta(seconds=lock_seconds),
                "attempt": job.attempt + 1,
            }
        )
        self.evals[job_id] = updated
        return updated

    async def requeue_eval(self, job_id: UUID) -> None:
        job = self.evals[job_id]
        self.evals[job_id] = job.model_copy(
            update={"status": "queued", "locked_at": None, "started_at": None}
        )

    async def claim_eval_jobs(self, limit: int, lock_seconds: int) -> list[EvalJob]:
        now = datetime.now(UTC)
        claimed: list[EvalJob] = []
        candidates = sorted(
            self.evals.values(),
            key=lambda job: job.created_at or now,
        )
        for job in candidates:
            if len(claimed) >= limit:
                break
            stale = (
                job.status == "running"
                and job.locked_at is not None
                and job.locked_at < now
            )
            if job.status == "queued" or stale:
                updated = job.model_copy(
                    update={
                        "status": "running",
                        "started_at": now,
                        "locked_at": now + timedelta(seconds=lock_seconds),
                        "attempt": job.attempt + 1,
                    }
                )
                self.evals[job.job_id] = updated
                claimed.append(updated)
        return claimed

    async def complete_eval(self, job_id: UUID, outcome: EvalOutcome) -> None:
        job = self.evals[job_id]
        self.evals[job_id] = job.model_copy(
            update={
                "status": outcome.status,
                "context_relevance": outcome.context_relevance,
                "hallucination_label": outcome.hallucination_label,
                "rationale": outcome.rationale,
                "error_message": outcome.error_message,
                "judge_model": outcome.judge_model or job.judge_model,
                "finished_at": datetime.now(UTC),
                "locked_at": None,
            }
        )
