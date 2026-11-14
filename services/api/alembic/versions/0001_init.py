"""Initial schema: genai_events, mcp_events, eval_jobs (SPEC §7).

Revision ID: 0001_init
Revises:
Create Date: 2026-11-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE genai_events (
            event_id            uuid PRIMARY KEY,
            schema_version      text NOT NULL,
            received_at         timestamptz NOT NULL DEFAULT now(),
            occurred_at         timestamptz NOT NULL,
            environment         text NOT NULL,
            sdk_name            text NOT NULL,
            sdk_version         text NOT NULL,
            provider            text NOT NULL,
            model               text NOT NULL,
            operation           text NOT NULL,
            prompt_version      text,
            trace_id            text NOT NULL,
            span_id             text NOT NULL,
            parent_span_id      text,
            input_tokens        integer,
            output_tokens       integer,
            reasoning_tokens    integer,
            cache_read_tokens   integer,
            cache_write_tokens  integer,
            ttft_ms             double precision,
            latency_ms          double precision NOT NULL,
            estimated_cost_usd  numeric(18, 8),
            catalog_version     text,
            price_status        text NOT NULL,
            status              text NOT NULL,
            error_type          text,
            metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT genai_price_status CHECK (price_status IN ('priced', 'unpriced')),
            CONSTRAINT genai_status CHECK (status IN ('ok', 'error'))
        );

        CREATE INDEX genai_events_occurred_idx ON genai_events (occurred_at DESC);
        CREATE INDEX genai_events_trace_idx ON genai_events (trace_id);
        CREATE INDEX genai_events_model_idx ON genai_events (provider, model, occurred_at DESC);
        CREATE INDEX genai_events_prompt_idx ON genai_events (prompt_version, occurred_at DESC);

        CREATE TABLE mcp_events (
            event_id        uuid PRIMARY KEY,
            schema_version  text NOT NULL,
            received_at     timestamptz NOT NULL DEFAULT now(),
            occurred_at     timestamptz NOT NULL,
            environment     text NOT NULL,
            server_name     text NOT NULL,
            transport       text NOT NULL,
            method          text NOT NULL,
            tool_name       text,
            jsonrpc_id      text,
            latency_ms      double precision NOT NULL,
            payload_bytes   integer NOT NULL,
            status          text NOT NULL,
            error_code      integer,
            error_type      text,
            trace_id        text NOT NULL,
            CONSTRAINT mcp_transport CHECK (transport IN ('stdio', 'streamable_http')),
            CONSTRAINT mcp_status CHECK (status IN ('ok', 'error'))
        );

        CREATE INDEX mcp_events_occurred_idx ON mcp_events (occurred_at DESC);
        CREATE INDEX mcp_events_tool_idx ON mcp_events (server_name, tool_name, occurred_at DESC);
        CREATE INDEX mcp_events_trace_idx ON mcp_events (trace_id);

        CREATE TABLE eval_jobs (
            job_id                uuid PRIMARY KEY,
            schema_version        text NOT NULL,
            status                text NOT NULL,
            rubric_version        text NOT NULL,
            judge_model           text,
            trace_id              text,
            query                 text NOT NULL,
            contexts              jsonb NOT NULL,
            answer                text NOT NULL,
            context_relevance     double precision,
            hallucination_label   text,
            rationale             text,
            error_message         text,
            attempt               integer NOT NULL DEFAULT 0,
            created_at            timestamptz NOT NULL DEFAULT now(),
            started_at            timestamptz,
            finished_at           timestamptz,
            locked_at             timestamptz,
            CONSTRAINT eval_status CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
            CONSTRAINT eval_label CHECK (
                hallucination_label IS NULL
                OR hallucination_label IN ('supported', 'partial', 'unsupported')
            )
        );

        CREATE INDEX eval_jobs_claim_idx ON eval_jobs (status, locked_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS eval_jobs;
        DROP TABLE IF EXISTS mcp_events;
        DROP TABLE IF EXISTS genai_events;
        """
    )
