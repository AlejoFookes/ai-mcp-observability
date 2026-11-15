"""Streamlit UI for the Acme Shop RAG demo.

Run from examples/rag-chat:
  uv sync
  uv run streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from openai import OpenAI

from rag_chat.bot import PROMPT_VERSIONS, answer_question, configure_telemetry
from rag_chat.config import Settings, load_env_files, load_settings
from rag_chat.index import Corpus, build_corpus

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

load_env_files(ROOT)


@st.cache_resource(show_spinner="Indexando políticas…")
def _boot() -> tuple[OpenAI, Settings, Corpus]:
    settings = load_settings()
    configure_telemetry(settings)
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    corpus = build_corpus(
        client,
        DATA_DIR,
        retrieval=settings.retrieval,
        embed_model=settings.embed_model,
    )
    return client, settings, corpus


def main() -> None:
    st.set_page_config(page_title="Acme support · multiMCP demo", page_icon="📦")
    st.title("Acme Shop — soporte RAG")
    st.caption(
        "Cada respuesta emite telemetría vía multimcp → tu API local. "
        "Usá el dashboard FinOps / Latency / Traces / Compare para ver el costo."
    )

    try:
        client, settings, corpus = _boot()
    except Exception as exc:  # noqa: BLE001 — show setup errors in the UI
        st.error(str(exc))
        st.info(
            "Poné `OPENAI_API_KEY` en el `.env` de la raíz del repo (key Groq `gsk_…`) "
            "o en `examples/rag-chat/.env`. Reiniciá Streamlit. "
            "API multiMCP en :8000 con el mismo `INGEST_TOKEN` / `MULTIMCP_INGEST_TOKEN`."
        )
        return

    with st.sidebar:
        st.subheader("Experimento FinOps")
        prompt_version = st.selectbox(
            "prompt_version",
            options=list(PROMPT_VERSIONS.keys()),
            index=0,
            help="Cambiá v1↔v2 y compará en el dashboard (Compare → prompt_version).",
        )
        st.text(f"Modelo chat: {settings.chat_model}")
        st.text(f"Base URL: {settings.openai_base_url}")
        st.text(f"Retrieval: {settings.retrieval} ({corpus.mode})")
        st.text(f"Ingest: {settings.ingest_url}")
        st.markdown(
            "Dashboard: [http://127.0.0.1:5173](http://127.0.0.1:5173)  \n"
            f"Token del shell: `{settings.ingest_token or '(vacío)'}`"
        )
        st.markdown(
            "Ideas de prueba:\n"
            "- *¿Cuántos días tengo para devolver un auricular?*\n"
            "- *¿Cuánto sale el envío Express?*\n"
            "- *¿La garantía cubre daño por líquido?*"
        )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("meta"):
                st.caption(msg["meta"])

    question = st.chat_input("Preguntá sobre devoluciones, envíos o garantía…")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Recuperando contexto y generando…"):
            try:
                result = answer_question(
                    client=client,
                    settings=settings,
                    corpus=corpus,
                    question=question,
                    prompt_version=prompt_version,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falló la llamada al modelo: {exc}")
                return

        st.markdown(result.text)
        sources = ", ".join(sorted({c.source for c in result.contexts})) or "—"
        meta = (
            f"`prompt_version={result.prompt_version}` · "
            f"`trace_id={result.trace_id}` · fuentes: {sources}"
        )
        st.caption(meta)
        st.session_state.messages.append(
            {"role": "assistant", "content": result.text, "meta": meta}
        )
        st.info(
            "Pegá el `trace_id` en el dashboard → Traces. "
            "Después corré 2–3 preguntas con **support-v1** y otras con **support-v2**, "
            "y abrí Compare."
        )


if __name__ == "__main__":
    main()
