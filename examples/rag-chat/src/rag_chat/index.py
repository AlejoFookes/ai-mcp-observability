from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from openai import OpenAI

_TOKEN = re.compile(r"[a-z0-9áéíóúñü]+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Chunk:
    source: str
    text: str


@dataclass(slots=True)
class Corpus:
    chunks: list[Chunk]
    embeddings: np.ndarray
    mode: str  # "lexical" | "embeddings"
    vocab: dict[str, int] | None = None


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


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _lexical_matrix(texts: list[str]) -> tuple[np.ndarray, dict[str, int]]:
    vocab: dict[str, int] = {}
    tokenized = [_tokenize(t) for t in texts]
    for tokens in tokenized:
        for tok in tokens:
            if tok not in vocab:
                vocab[tok] = len(vocab)
    if not vocab:
        return np.zeros((len(texts), 1), dtype=np.float32), vocab
    matrix = np.zeros((len(texts), len(vocab)), dtype=np.float32)
    for row, tokens in enumerate(tokenized):
        for tok in tokens:
            matrix[row, vocab[tok]] += 1.0
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms, vocab


def embed_texts(client: OpenAI, model: str, texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    response = client.embeddings.create(model=model, input=texts)
    vectors = [item.embedding for item in response.data]
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def build_corpus(
    client: OpenAI,
    data_dir: Path,
    *,
    retrieval: str,
    embed_model: str,
) -> Corpus:
    chunks = load_markdown_chunks(data_dir)
    if not chunks:
        raise RuntimeError(f"No markdown docs found under {data_dir}")
    texts = [c.text for c in chunks]
    if retrieval == "embeddings":
        embeddings = embed_texts(client, embed_model, texts)
        return Corpus(chunks=chunks, embeddings=embeddings, mode="embeddings", vocab=None)
    matrix, vocab = _lexical_matrix(texts)
    return Corpus(chunks=chunks, embeddings=matrix, mode="lexical", vocab=vocab)


def retrieve(
    corpus: Corpus,
    *,
    query: str,
    client: OpenAI | None = None,
    embed_model: str = "",
    top_k: int = 3,
) -> list[Chunk]:
    if not corpus.chunks:
        return []
    if corpus.mode == "embeddings":
        if client is None:
            raise ValueError("embeddings retrieval requires an OpenAI client")
        query_vec = embed_texts(client, embed_model, [query])[0]
    else:
        vocab = corpus.vocab or {}
        vec = np.zeros((corpus.embeddings.shape[1],), dtype=np.float32)
        for tok in _tokenize(query):
            idx = vocab.get(tok)
            if idx is not None:
                vec[idx] += 1.0
        norm = float(np.linalg.norm(vec))
        query_vec = vec / norm if norm else vec

    if corpus.embeddings.size == 0:
        return corpus.chunks[:top_k]
    q = query_vec.astype(np.float32)
    norm = float(np.linalg.norm(q))
    if norm == 0:
        return corpus.chunks[:top_k]
    q = q / norm
    scores = corpus.embeddings @ q
    k = min(top_k, len(corpus.chunks))
    idxs = np.argsort(scores)[::-1][:k]
    return [corpus.chunks[int(i)] for i in idxs]
