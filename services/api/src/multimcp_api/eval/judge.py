"""OpenAI-compatible judge via multimcp wrap_openai (SPEC §8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from multimcp import wrap_openai

RUBRIC_VERSION = "rag-judge-1.0"
_RUBRIC_PATH = Path(__file__).parent / "rubrics" / "rag_judge_1_0.txt"


class JudgeVerdict(BaseModel):
    context_relevance: float = Field(ge=0.0, le=1.0)
    hallucination_label: Literal["supported", "partial", "unsupported"]
    rationale: str = Field(min_length=1, max_length=500)


class JudgeClient(Protocol):
    async def judge(self, *, query: str, contexts: list[str], answer: str) -> JudgeVerdict: ...


class OpenAIJudgeClient:
    """Calls responses.create through wrap_openai with metadata.role=judge."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        client: Any | None = None,
    ) -> None:
        if not model:
            raise ValueError("JUDGE_MODEL is required for the RAG evaluator")
        if client is None:
            from openai import OpenAI

            raw = OpenAI(api_key=api_key or "unused", base_url=base_url)
        else:
            raw = client
        self._model = model
        self._client = wrap_openai(
            raw,
            metadata={"role": "judge", "rubric_version": RUBRIC_VERSION},
        )
        self._rubric = _RUBRIC_PATH.read_text(encoding="utf-8")

    async def judge(self, *, query: str, contexts: list[str], answer: str) -> JudgeVerdict:
        prompt = self._build_prompt(query=query, contexts=contexts, answer=answer)
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = self._client.responses.create(
                    model=self._model,
                    input=prompt,
                    temperature=0,
                )
                text = _response_text(response)
                return JudgeVerdict.model_validate(json.loads(text))
            except (json.JSONDecodeError, ValidationError, TypeError, KeyError) as exc:
                last_error = exc
                continue
        raise RuntimeError(f"judge returned invalid JSON after retry: {last_error}")

    def _build_prompt(self, *, query: str, contexts: list[str], answer: str) -> str:
        numbered = "\n".join(f"[{index}] {fragment}" for index, fragment in enumerate(contexts))
        return (
            f"{self._rubric}\n\n"
            f"query:\n{query}\n\n"
            f"contexts:\n{numbered}\n\n"
            f"answer:\n{answer}\n"
        )


def _response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    output = getattr(response, "output", None)
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                value = getattr(content, "text", None)
                if isinstance(value, str):
                    chunks.append(value)
        if chunks:
            return "".join(chunks).strip()
    raise TypeError("judge response had no text")
