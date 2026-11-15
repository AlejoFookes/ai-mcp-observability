from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from multimcp.models import SCHEMA_VERSION
from multimcp_api.domain.models import EvalStatus, HallucinationLabel
from multimcp_api.schemas.common import ApiModel

MAX_QUERY_BYTES = 16 * 1024
MAX_ANSWER_BYTES = 16 * 1024
MAX_CONTEXTS = 20
MAX_TOTAL_BYTES = 64 * 1024


class EvaluationCreateRequest(ApiModel):
    schema_version: Literal["1.0"]
    rubric_version: Literal["rag-judge-1.0"] = "rag-judge-1.0"
    trace_id: str | None = None
    query: str = Field(min_length=1)
    contexts: list[str] = Field(min_length=1, max_length=MAX_CONTEXTS)
    answer: str = Field(min_length=1)

    @field_validator("query", "answer")
    @classmethod
    def _byte_limits(cls, value: str) -> str:
        limit = MAX_QUERY_BYTES
        if len(value.encode("utf-8")) > limit:
            raise ValueError(f"field exceeds {limit} bytes")
        return value

    @model_validator(mode="after")
    def _total_size(self) -> EvaluationCreateRequest:
        total = len(self.query.encode("utf-8")) + len(self.answer.encode("utf-8"))
        total += sum(len(item.encode("utf-8")) for item in self.contexts)
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f"evaluation payload exceeds {MAX_TOTAL_BYTES} bytes")
        return self


class EvaluationAcceptedResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    job_id: UUID
    status: Literal["queued"] = "queued"


class EvaluationJobResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    job_id: UUID
    status: EvalStatus
    rubric_version: str
    judge_model: str | None = None
    trace_id: str | None = None
    query: str
    contexts: list[str]
    answer: str
    context_relevance: float | None = None
    hallucination_label: HallucinationLabel | None = None
    rationale: str | None = None
    error_message: str | None = None
    attempt: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
