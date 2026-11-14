"""Process settings. Values come only from the environment (SPEC §6)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

StorageBackend = Literal["postgres", "bigquery"]
EvalBackend = Literal["postgres", "inline"]

_DEFAULT_DATABASE_URL = "postgresql+asyncpg://multimcp:multimcp@localhost:5432/multimcp"


def _asyncpg_to_psycopg(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    storage_backend: StorageBackend = Field(default="postgres", alias="STORAGE_BACKEND")
    database_url: str = Field(default=_DEFAULT_DATABASE_URL, alias="DATABASE_URL")
    alembic_database_url: str | None = Field(default=None, alias="ALEMBIC_DATABASE_URL")
    ingest_token: str = Field(default="", alias="INGEST_TOKEN")
    eval_backend: EvalBackend = Field(default="postgres", alias="EVAL_BACKEND")
    judge_base_url: str = Field(default="https://api.openai.com/v1", alias="JUDGE_BASE_URL")
    judge_model: str = Field(default="", alias="JUDGE_MODEL")
    judge_api_key: str = Field(default="", alias="JUDGE_API_KEY", repr=False)
    bq_project: str = Field(default="", alias="BQ_PROJECT")
    bq_dataset: str = Field(default="multimcp", alias="BQ_DATASET")

    @field_validator("storage_backend", "eval_backend", mode="before")
    @classmethod
    def _lower(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower()
        return value

    @property
    def resolved_alembic_database_url(self) -> str:
        if self.alembic_database_url:
            return self.alembic_database_url
        return _asyncpg_to_psycopg(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
