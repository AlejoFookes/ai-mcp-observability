"""PostgreSQL EventRepository (asyncpg + SQLAlchemy 2)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from multimcp.models import GenAIEvent, McpEvent
from multimcp_api.domain.models import (
    CompareQuery,
    CompareResult,
    CompareSide,
    EvalJob,
    EvalOutcome,
    FinOpsRow,
    InsertResult,
    LatencyRow,
    TraceSpan,
    WindowQuery,
)
from multimcp_api.repositories.orm import EvalJobRow, GenAIEventRow, McpEventRow


class PostgresEventRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def insert_genai(self, events: Sequence[GenAIEvent]) -> InsertResult:
        if not events:
            return InsertResult(accepted=0, duplicates=0)
        rows = [_genai_values(event) for event in events]
        async with self._session_factory() as session:
            stmt = (
                insert(GenAIEventRow)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["event_id"])
            )
            result = await session.execute(stmt)
            await session.commit()
            accepted = result.rowcount or 0
        return InsertResult(accepted=accepted, duplicates=len(events) - accepted)

    async def insert_mcp(self, events: Sequence[McpEvent]) -> InsertResult:
        if not events:
            return InsertResult(accepted=0, duplicates=0)
        rows = [_mcp_values(event) for event in events]
        async with self._session_factory() as session:
            stmt = (
                insert(McpEventRow)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["event_id"])
            )
            result = await session.execute(stmt)
            await session.commit()
            accepted = result.rowcount or 0
        return InsertResult(accepted=accepted, duplicates=len(events) - accepted)

    async def finops_summary(self, query: WindowQuery) -> list[FinOpsRow]:
        if query.group_by == "mcp_server":
            return await self._finops_mcp(query)
        return await self._finops_genai(query)

    async def _finops_genai(self, query: WindowQuery) -> list[FinOpsRow]:
        key_expr = _genai_key_sql(query.group_by)
        judge_clause = ""
        if not query.include_judge:
            judge_clause = "AND coalesce(metadata->>'role', '') <> 'judge'"
        sql = text(
            f"""
            SELECT
                {key_expr} AS key,
                count(*)::int AS request_count,
                count(*) FILTER (WHERE status = 'error')::int AS error_count,
                coalesce(sum(input_tokens), 0)::int AS input_tokens,
                coalesce(sum(output_tokens), 0)::int AS output_tokens,
                coalesce(sum(estimated_cost_usd) FILTER (WHERE price_status = 'priced'), 0)
                    AS estimated_cost_usd,
                count(*) FILTER (WHERE price_status = 'unpriced')::int AS unpriced_count
            FROM genai_events
            WHERE occurred_at >= :start AND occurred_at < :end
            {judge_clause}
            GROUP BY 1
            ORDER BY 1
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(
                sql, {"start": query.start, "end": query.end}
            )
            return [
                FinOpsRow(
                    key=row.key,
                    request_count=row.request_count,
                    error_count=row.error_count,
                    input_tokens=row.input_tokens,
                    output_tokens=row.output_tokens,
                    estimated_cost_usd=Decimal(str(row.estimated_cost_usd)),
                    unpriced_count=row.unpriced_count,
                )
                for row in result
            ]

    async def _finops_mcp(self, query: WindowQuery) -> list[FinOpsRow]:
        sql = text(
            """
            SELECT
                server_name AS key,
                count(*)::int AS request_count,
                count(*) FILTER (WHERE status = 'error')::int AS error_count
            FROM mcp_events
            WHERE occurred_at >= :start AND occurred_at < :end
            GROUP BY server_name
            ORDER BY server_name
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(
                sql, {"start": query.start, "end": query.end}
            )
            return [
                FinOpsRow(
                    key=row.key,
                    request_count=row.request_count,
                    error_count=row.error_count,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost_usd=Decimal("0"),
                    unpriced_count=0,
                )
                for row in result
            ]

    async def latency(self, query: WindowQuery) -> list[LatencyRow]:
        if query.group_by == "mcp_tool":
            return await self._latency_mcp(query)
        return await self._latency_genai(query)

    async def _latency_genai(self, query: WindowQuery) -> list[LatencyRow]:
        key_expr = _genai_key_sql(query.group_by)
        sql = text(
            f"""
            SELECT
                {key_expr} AS key,
                count(*)::int AS count,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
                (count(*) FILTER (WHERE status = 'error')::float / count(*)) AS error_rate
            FROM genai_events
            WHERE occurred_at >= :start AND occurred_at < :end
            GROUP BY 1
            ORDER BY 1
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(
                sql, {"start": query.start, "end": query.end}
            )
            return [
                LatencyRow(
                    key=row.key,
                    count=row.count,
                    p50_ms=float(row.p50_ms),
                    p95_ms=float(row.p95_ms),
                    error_rate=float(row.error_rate),
                )
                for row in result
            ]

    async def _latency_mcp(self, query: WindowQuery) -> list[LatencyRow]:
        sql = text(
            """
            SELECT
                CASE
                    WHEN tool_name IS NULL OR tool_name = '' THEN server_name
                    ELSE server_name || '/' || tool_name
                END AS key,
                count(*)::int AS count,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
                (count(*) FILTER (WHERE status = 'error')::float / count(*)) AS error_rate
            FROM mcp_events
            WHERE occurred_at >= :start AND occurred_at < :end
            GROUP BY 1
            ORDER BY 1
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(
                sql, {"start": query.start, "end": query.end}
            )
            return [
                LatencyRow(
                    key=row.key,
                    count=row.count,
                    p50_ms=float(row.p50_ms),
                    p95_ms=float(row.p95_ms),
                    error_rate=float(row.error_rate),
                )
                for row in result
            ]

    async def get_trace(self, trace_id: str) -> list[TraceSpan]:
        async with self._session_factory() as session:
            genai = await session.execute(
                select(GenAIEventRow)
                .where(GenAIEventRow.trace_id == trace_id)
                .order_by(GenAIEventRow.occurred_at)
            )
            mcp = await session.execute(
                select(McpEventRow)
                .where(McpEventRow.trace_id == trace_id)
                .order_by(McpEventRow.occurred_at)
            )
            spans: list[TraceSpan] = []
            for row in genai.scalars():
                spans.append(
                    TraceSpan(
                        kind="genai",
                        event_id=row.event_id,
                        occurred_at=row.occurred_at,
                        trace_id=row.trace_id,
                        status=row.status,
                        latency_ms=float(row.latency_ms),
                        label=f"{row.provider}/{row.model}",
                        detail={
                            "operation": row.operation,
                            "prompt_version": row.prompt_version,
                        },
                    )
                )
            for row in mcp.scalars():
                spans.append(
                    TraceSpan(
                        kind="mcp",
                        event_id=row.event_id,
                        occurred_at=row.occurred_at,
                        trace_id=row.trace_id,
                        status=row.status,
                        latency_ms=float(row.latency_ms),
                        label=row.tool_name or row.method,
                        detail={
                            "server_name": row.server_name,
                            "method": row.method,
                            "tool_name": row.tool_name,
                        },
                    )
                )
            spans.sort(key=lambda span: span.occurred_at)
            return spans

    async def compare(self, query: CompareQuery) -> CompareResult:
        return CompareResult(
            left=await self._compare_side(query, query.left),
            right=await self._compare_side(query, query.right),
        )

    async def _compare_side(self, query: CompareQuery, key: str) -> CompareSide:
        if query.dimension == "prompt_version":
            match = "coalesce(prompt_version, '') = :key"
        else:
            match = "(provider || '/' || model) = :key"
        sql = text(
            f"""
            SELECT
                count(*)::int AS request_count,
                count(*) FILTER (WHERE status = 'error')::int AS error_count,
                coalesce(sum(input_tokens), 0)::int AS input_tokens,
                coalesce(sum(output_tokens), 0)::int AS output_tokens,
                coalesce(sum(estimated_cost_usd) FILTER (WHERE price_status = 'priced'), 0)
                    AS estimated_cost_usd,
                count(*) FILTER (WHERE price_status = 'unpriced')::int AS unpriced_count,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms
            FROM genai_events
            WHERE occurred_at >= :start AND occurred_at < :end
              AND {match}
            """
        )
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    sql, {"start": query.start, "end": query.end, "key": key}
                )
            ).one()
        if row.request_count == 0:
            return CompareSide(
                key=key,
                request_count=0,
                error_count=0,
                input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=Decimal("0"),
                unpriced_count=0,
                p50_ms=None,
                p95_ms=None,
                error_rate=0.0,
            )
        return CompareSide(
            key=key,
            request_count=row.request_count,
            error_count=row.error_count,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            estimated_cost_usd=Decimal(str(row.estimated_cost_usd)),
            unpriced_count=row.unpriced_count,
            p50_ms=float(row.p50_ms),
            p95_ms=float(row.p95_ms),
            error_rate=row.error_count / row.request_count,
        )

    async def enqueue_eval(self, job: EvalJob) -> None:
        async with self._session_factory() as session:
            session.add(
                EvalJobRow(
                    job_id=job.job_id,
                    schema_version=job.schema_version,
                    status="queued",
                    rubric_version=job.rubric_version,
                    judge_model=job.judge_model,
                    trace_id=job.trace_id,
                    query=job.query,
                    contexts=job.contexts,
                    answer=job.answer,
                )
            )
            await session.commit()

    async def claim_eval_jobs(self, limit: int, lock_seconds: int) -> list[EvalJob]:
        sql = text(
            """
            UPDATE eval_jobs
            SET status = 'running',
                started_at = now(),
                locked_at = now() + make_interval(secs => :lock_seconds),
                attempt = attempt + 1
            WHERE job_id IN (
                SELECT job_id FROM eval_jobs
                WHERE status = 'queued'
                   OR (status = 'running' AND locked_at < now())
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT :limit
            )
            RETURNING *
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(
                sql, {"limit": limit, "lock_seconds": lock_seconds}
            )
            rows = result.mappings().all()
            await session.commit()
        return [_eval_from_mapping(row) for row in rows]

    async def complete_eval(self, job_id: UUID, outcome: EvalOutcome) -> None:
        sql = text(
            """
            UPDATE eval_jobs
            SET status = :status,
                context_relevance = :context_relevance,
                hallucination_label = :hallucination_label,
                rationale = :rationale,
                error_message = :error_message,
                judge_model = coalesce(:judge_model, judge_model),
                finished_at = now(),
                locked_at = NULL
            WHERE job_id = :job_id
            """
        )
        async with self._session_factory() as session:
            await session.execute(
                sql,
                {
                    "job_id": job_id,
                    "status": outcome.status,
                    "context_relevance": outcome.context_relevance,
                    "hallucination_label": outcome.hallucination_label,
                    "rationale": outcome.rationale,
                    "error_message": outcome.error_message,
                    "judge_model": outcome.judge_model,
                },
            )
            await session.commit()


def _genai_key_sql(group_by: str) -> str:
    if group_by == "model":
        return "provider || '/' || model"
    if group_by == "provider":
        return "provider"
    if group_by == "prompt_version":
        return "coalesce(prompt_version, '')"
    if group_by == "operation":
        return "operation"
    raise ValueError(f"unsupported genai group_by: {group_by}")


def _genai_values(event: GenAIEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "schema_version": event.schema_version,
        "occurred_at": event.occurred_at,
        "environment": event.environment,
        "sdk_name": event.sdk_name,
        "sdk_version": event.sdk_version,
        "provider": event.provider,
        "model": event.model,
        "operation": event.operation,
        "prompt_version": event.prompt_version,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "parent_span_id": event.parent_span_id,
        "input_tokens": event.input_tokens,
        "output_tokens": event.output_tokens,
        "reasoning_tokens": event.reasoning_tokens,
        "cache_read_tokens": event.cache_read_tokens,
        "cache_write_tokens": event.cache_write_tokens,
        "ttft_ms": event.ttft_ms,
        "latency_ms": event.latency_ms,
        "estimated_cost_usd": event.estimated_cost_usd,
        "catalog_version": event.catalog_version,
        "price_status": event.price_status,
        "status": event.status,
        "error_type": event.error_type,
        "metadata_json": dict(event.metadata),
    }


def _mcp_values(event: McpEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "schema_version": event.schema_version,
        "occurred_at": event.occurred_at,
        "environment": event.environment,
        "server_name": event.server_name,
        "transport": event.transport,
        "method": event.method,
        "tool_name": event.tool_name,
        "jsonrpc_id": event.jsonrpc_id,
        "latency_ms": event.latency_ms,
        "payload_bytes": event.payload_bytes,
        "status": event.status,
        "error_code": event.error_code,
        "error_type": event.error_type,
        "trace_id": event.trace_id,
    }


def _eval_from_mapping(row: Any) -> EvalJob:
    return EvalJob(
        job_id=row["job_id"],
        schema_version=row["schema_version"],
        status=row["status"],
        rubric_version=row["rubric_version"],
        judge_model=row["judge_model"],
        trace_id=row["trace_id"],
        query=row["query"],
        contexts=list(row["contexts"]),
        answer=row["answer"],
        context_relevance=row["context_relevance"],
        hallucination_label=row["hallucination_label"],
        rationale=row["rationale"],
        error_message=row["error_message"],
        attempt=row["attempt"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        locked_at=row["locked_at"],
    )


def create_async_engine(database_url: str) -> AsyncEngine:
    from sqlalchemy.ext.asyncio import create_async_engine as _create

    return _create(database_url, pool_pre_ping=True)
