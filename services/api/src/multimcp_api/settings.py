"""Process settings. Values come only from the environment (SPEC §6)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

StorageBackend = Literal["postgres", "bigquery", "memory"]
EvalBackend = Literal["postgres", "inline"]

_DEFAULT_DATABASE_URL = "postgresql+asyncpg://multimcp:multimcp@localhost:5432/multimcp"


def _asyncpg_to_psycopg(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def _discover_dotenv_file() -> Path | None:
    """Nearest `.env` walking up from cwd, else from this package (local DX)."""
    for start in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        for parent in (start, *start.parents):
            candidate = parent / ".env"
            if candidate.is_file():
                return candidate
            if parent.parent == parent:
                break
    return None


def _load_dotenv_into_environ() -> None:
    """Fill empty/missing os.environ keys from `.env` (last duplicate line wins)."""
    path = _discover_dotenv_file()
    if path is None:
        return
    parsed: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        parsed[key] = value.strip().strip('"').strip("'")
    for key, value in parsed.items():
        current = os.environ.get(key)
        if current is None or current.strip() == "":
            os.environ[key] = value


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
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY", repr=False)
    # Playground defaults to Groq (OpenAI-compatible). Override for OpenAI/Ollama.
    openai_base_url: str = Field(
        default="https://api.groq.com/openai/v1", alias="OPENAI_BASE_URL"
    )
    playground_default_left: str = Field(
        default="openai/gpt-oss-20b", alias="PLAYGROUND_LEFT_MODEL"
    )
    playground_default_right: str = Field(
        default="openai/gpt-oss-120b", alias="PLAYGROUND_RIGHT_MODEL"
    )
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
    _load_dotenv_into_environ()
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
