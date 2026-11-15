"""Run the same prompt on two models via wrap_openai (demo / bakeoff)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from multimcp import configure, prompt_context, wrap_openai
from multimcp.exporters.base import Event
from multimcp.models import GenAIEvent, McpEvent

from multimcp_api.errors import AppError
from multimcp_api.repositories.base import EventRepository
from multimcp_api.settings import Settings

logger = logging.getLogger("multimcp_api")


@dataclass(frozen=True, slots=True)
class DualSide:
    model: str
    answer: str
    latency_ms: float


@dataclass(frozen=True, slots=True)
class DualResult:
    trace_id: str
    prompt_version: str
    left: DualSide
    right: DualSide


@dataclass
class _BufferExporter:
    """In-process exporter — avoids HTTP self-POST deadlocks on a single Uvicorn worker."""

    _events: list[Event] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def insert(self, events: Sequence[Event]) -> None:
        with self._lock:
            self._events.extend(events)

    def drain(self) -> list[Event]:
        with self._lock:
            out = list(self._events)
            self._events.clear()
            return out


def _completion_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", None)
    return (content or "").strip()


def _resolve_api_key(settings: Settings) -> str:
    key = settings.openai_api_key.strip() or settings.judge_api_key.strip()
    if not key:
        raise AppError(
            503,
            "storage_unavailable",
            "OPENAI_API_KEY (or JUDGE_API_KEY) is required for the playground",
        )
    return key


async def run_dual_completion(
    settings: Settings,
    repository: EventRepository,
    *,
    prompt: str,
    left_model: str,
    right_model: str,
    prompt_version: str,
) -> DualResult:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AppError(
            503,
            "storage_unavailable",
            "Install multimcp-api[judge] (openai) to use the playground",
        ) from exc

    api_key = _resolve_api_key(settings)
    exporter = _BufferExporter()
    configure(exporter=exporter)

    raw = OpenAI(api_key=api_key, base_url=settings.openai_base_url or settings.judge_base_url)
    client = wrap_openai(raw)
    trace_id = str(uuid4())
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Answer clearly and concisely. "
                "If the user writes in Spanish, reply in Spanish."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    def _one(model: str) -> DualSide:
        started = time.perf_counter()
        with prompt_context(
            prompt_version=prompt_version,
            environment="playground",
            trace_id=trace_id,
        ):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
            )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        text = _completion_text(response) or "(empty model response)"
        return DualSide(model=model, answer=text, latency_ms=elapsed_ms)

    try:
        left = _one(left_model)
        right = _one(right_model)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(502, "internal_error", f"model call failed: {exc}") from exc
    finally:
        buffered = exporter.drain()
        genai = [e for e in buffered if isinstance(e, GenAIEvent)]
        mcp = [e for e in buffered if isinstance(e, McpEvent)]
        try:
            if genai:
                await repository.insert_genai(genai)
            if mcp:
                await repository.insert_mcp(mcp)
        except Exception:
            logger.exception("playground: failed to persist telemetry events")

    return DualResult(
        trace_id=trace_id,
        prompt_version=prompt_version,
        left=left,
        right=right,
    )
