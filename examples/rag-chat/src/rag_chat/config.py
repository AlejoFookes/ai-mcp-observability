from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    openai_api_key: str
    ingest_url: str
    ingest_token: str
    chat_model: str
    embed_model: str


def load_settings() -> Settings:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Copy .env.example to .env and set the key."
        )
    return Settings(
        openai_api_key=key,
        ingest_url=os.environ.get("MULTIMCP_INGEST_URL", "http://127.0.0.1:8000").rstrip(
            "/"
        ),
        ingest_token=os.environ.get("MULTIMCP_INGEST_TOKEN", "").strip(),
        chat_model=os.environ.get("RAG_CHAT_MODEL", "gpt-4.1-mini").strip()
        or "gpt-4.1-mini",
        embed_model=os.environ.get("RAG_EMBED_MODEL", "text-embedding-3-small").strip()
        or "text-embedding-3-small",
    )
