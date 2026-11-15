from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    openai_api_key: str
    openai_base_url: str
    ingest_url: str
    ingest_token: str
    chat_model: str
    embed_model: str
    retrieval: str  # "lexical" | "embeddings"


def load_env_files(example_root: Path) -> None:
    """Load optional local `.env`, then repo-root `.env` (root wins for shared keys)."""
    load_dotenv(example_root / ".env", override=False)
    repo_env = example_root.parent.parent / ".env"
    if repo_env.is_file():
        load_dotenv(repo_env, override=True)


def load_settings() -> Settings:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Set it in the repo-root .env "
            "(or examples/rag-chat/.env). For Groq, use a gsk_ key from "
            "https://console.groq.com/keys."
        )

    base = (
        os.environ.get("OPENAI_BASE_URL", "").strip()
        or "https://api.openai.com/v1"
    )
    ingest_token = (
        os.environ.get("MULTIMCP_INGEST_TOKEN", "").strip()
        or os.environ.get("INGEST_TOKEN", "").strip()
    )
    using_groq = "groq.com" in base
    chat_default = "openai/gpt-oss-20b" if using_groq else "gpt-4.1-mini"
    retrieval = os.environ.get("RAG_RETRIEVAL", "").strip().lower()
    if not retrieval:
        retrieval = "lexical" if using_groq else "embeddings"
    if retrieval not in {"lexical", "embeddings"}:
        retrieval = "lexical"

    chat_model = os.environ.get("RAG_CHAT_MODEL", chat_default).strip() or chat_default
    # Stale local .env often still says gpt-4.1-mini while BASE_URL is Groq.
    if using_groq and chat_model.startswith("gpt-"):
        chat_model = chat_default

    return Settings(
        openai_api_key=key,
        openai_base_url=base.rstrip("/"),
        ingest_url=os.environ.get("MULTIMCP_INGEST_URL", "http://127.0.0.1:8000").rstrip(
            "/"
        ),
        ingest_token=ingest_token,
        chat_model=chat_model,
        embed_model=os.environ.get("RAG_EMBED_MODEL", "text-embedding-3-small").strip()
        or "text-embedding-3-small",
        retrieval=retrieval,
    )
