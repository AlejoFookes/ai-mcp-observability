from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from multimcp.models import SCHEMA_VERSION


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    status: Literal["ok", "degraded"]
    storage_backend: Literal["postgres", "bigquery"]


class IngestResponse(ApiModel):
    """Stub response for M3.1 auth coverage. Full ingest lands in M3.3."""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    accepted: int = Field(ge=0)
    duplicates: int = Field(ge=0)
