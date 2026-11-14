from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from openai import OpenAI


@dataclass(frozen=True, slots=True)
class Chunk:
    source: str
    text: str


@dataclass(slots=True)
class Corpus:
    chunks: list[Chunk]
    embeddings: np.ndarray


def load_markdown_chunks(data_dir: Path, *, max_chars: int = 700) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(data_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
        buf = ""
        for part in parts:
            candidate = f"{buf}\n\n{part}".strip() if buf else part
            if len(candidate) > max_chars and buf:
                chunks.append(Chunk(source=path.name, text=buf))
                buf = part
            else:
                buf = candidate
        if buf:
            chunks.append(Chunk(source=path.name, text=buf))
    return chunks


def embed_texts(client: OpenAI, model: str, texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    response = client.embeddings.create(model=model, input=texts)
    vectors = [item.embedding for item in response.data]
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def build_corpus(client: OpenAI, data_dir: Path, embed_model: str) -> Corpus:
    chunks = load_markdown_chunks(data_dir)
    if not chunks:
        raise RuntimeError(f"No markdown docs found under {data_dir}")
    embeddings = embed_texts(client, embed_model, [c.text for c in chunks])
    return Corpus(chunks=chunks, embeddings=embeddings)


def retrieve(corpus: Corpus, query_vec: np.ndarray, *, top_k: int = 3) -> list[Chunk]:
    if corpus.embeddings.size == 0:
        return []
    q = query_vec.astype(np.float32)
    norm = float(np.linalg.norm(q))
    if norm == 0:
        return []
    q = q / norm
    scores = corpus.embeddings @ q
    k = min(top_k, len(corpus.chunks))
    idxs = np.argsort(scores)[::-1][:k]
    return [corpus.chunks[int(i)] for i in idxs]
