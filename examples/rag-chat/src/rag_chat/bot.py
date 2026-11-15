from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import uuid4

from openai import OpenAI
from multimcp import configure, prompt_context, wrap_openai

from rag_chat.config import Settings
from rag_chat.index import Chunk, Corpus, retrieve

PROMPT_VERSIONS: dict[str, str] = {
    "support-v1": (
        "Sos el asistente de soporte de Acme Shop. Respondé en español, breve. "
        "Usá solo el contexto recuperado. Si no alcanza, pedí el dato que falta."
    ),
    "support-v2": (
        "Sos el asistente de soporte de Acme Shop. Respondé en español con tono claro. "
        "Citá la fuente (nombre de archivo) cuando uses una política. "
        "Si el contexto no cubre la pregunta, decilo y sugerí contactar soporte. "
        "No inventes plazos ni precios."
    ),
}


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    trace_id: str
    prompt_version: str
    contexts: list[Chunk]


def configure_telemetry(settings: Settings) -> None:
    """Point HttpExporter at the local API before wrapping the client."""
    os.environ["MULTIMCP_INGEST_URL"] = settings.ingest_url
    if settings.ingest_token:
        os.environ["MULTIMCP_INGEST_TOKEN"] = settings.ingest_token
    configure()


def answer_question(
    *,
    client: OpenAI,
    settings: Settings,
    corpus: Corpus,
    question: str,
    prompt_version: str,
) -> Answer:
    if prompt_version not in PROMPT_VERSIONS:
        raise ValueError(f"Unknown prompt_version: {prompt_version}")

    contexts = retrieve(
        corpus,
        query=question,
        client=client,
        embed_model=settings.embed_model,
        top_k=3,
    )
    context_block = "\n\n".join(
        f"[{c.source}]\n{c.text}" for c in contexts
    ) or "(sin contexto)"

    system = PROMPT_VERSIONS[prompt_version]
    user = (
        f"Contexto recuperado:\n{context_block}\n\n"
        f"Pregunta del cliente:\n{question}\n\n"
        "Respuesta:"
    )

    wrapped = wrap_openai(client)
    trace_id = str(uuid4())
    with prompt_context(
        prompt_version=prompt_version,
        environment="demo",
        trace_id=trace_id,
    ):
        completion = wrapped.chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )

    choice = completion.choices[0] if completion.choices else None
    text = ""
    if choice is not None and choice.message is not None:
        text = (choice.message.content or "").strip()
    if not text:
        text = "(sin respuesta del modelo)"

    return Answer(
        text=text,
        trace_id=trace_id,
        prompt_version=prompt_version,
        contexts=contexts,
    )
