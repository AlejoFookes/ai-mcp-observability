"""Run the same prompt on two models via wrap_openai (demo / bakeoff)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from multimcp import HttpExporter, configure, prompt_context, wrap_openai

from multimcp_api.errors import AppError
from multimcp_api.settings import Settings


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


def run_dual_completion(
    settings: Settings,
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
    exporter = HttpExporter(
        url="http://127.0.0.1:8000",
        token=settings.ingest_token or None,
        background=False,
    )
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
        exporter.flush()
        exporter.close()

    return DualResult(
        trace_id=trace_id,
        prompt_version=prompt_version,
        left=left,
        right=right,
    )
