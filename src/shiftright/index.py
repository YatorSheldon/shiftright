"""Search over chunks: BM25 keyword search, optional dense embeddings, fused.

BM25 is implemented directly (about 40 lines) so the core has no heavy
dependencies and runs anywhere, including CI. When an embedding function is
supplied (for example Ollama's ``nomic-embed-text``), results from both
retrievers are combined with reciprocal rank fusion, which needs no score
calibration between the two.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from shiftright.chunk import Chunk

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "but",
    "by",
    "can",
    "could",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "me",
    "my",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "should",
    "so",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "to",
    "up",
    "was",
    "we",
    "were",
    "what",
    "when",
    "which",
    "who",
    "will",
    "with",
    "would",
    "you",
    "your",
    "am",
    "get",
}
# Everyday words folded into the Act's vocabulary before indexing and searching.
# A value can expand to several tokens ("payslip" -> "pay slip", as the Act writes it).
SYNONYMS = {
    "casuals": "casual",
    "arvo": "afternoon",
    "uni": "university",
    "sacked": "dismissed",
    "fired": "dismissed",
    "dismissal": "dismissed",
    "sickie": "sick",
    "super": "superannuation",
    "intern": "internship",
    "interns": "internship",
    "boss": "employer",
    "payslip": "pay slip",
    "payslips": "pay slip",
    "coworkers": "employees",
    "colleagues": "employees",
}
HEADING_WEIGHT = 2.0  # a match in a section's heading counts double


def _stem(tok: str) -> str:
    for suffix in ("ings", "ing", "ies", "ed", "es", "s"):
        if tok.endswith(suffix) and len(tok) - len(suffix) >= 4:
            return tok[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return tok


def tokenize(text: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9]+", text.lower().replace("'", "")):
        if t in STOPWORDS:
            continue
        for part in SYNONYMS.get(t, t).split():
            out.append(_stem(part))
    return out


@dataclass
class Hit:
    chunk: Chunk
    score: float
    rank: int


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=float)
        self.avg = float(self.len.mean()) if len(docs) else 0.0
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tf))
        for i, tf in enumerate(self.tf):
            norm = self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1))
            s = 0.0
            for t in query:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            out[i] = s
        return out


class Index:
    """Hybrid retriever over a list of chunks."""

    def __init__(self, chunks: list[Chunk], embed: Callable[[list[str]], np.ndarray] | None = None, embeddings: np.ndarray | None = None):
        self.chunks = chunks
        self.bm25 = BM25([tokenize(c.search_text) for c in chunks])
        # Field weighting: a second index over just the heading and its Part/Division context.
        self.bm25_heading = BM25([tokenize(f"{c.heading} {c.context}") for c in chunks])
        self.embed = embed
        self.embeddings = embeddings
        if embed is not None and embeddings is None and chunks:
            self.embeddings = _normalise(embed([c.search_text for c in chunks]))

    def search(self, query: str, k: int = 5, rrf_k: int = 60) -> list[Hit]:
        if not self.chunks:
            return []
        q_toks = tokenize(query)
        bm = self.bm25.scores(q_toks) + HEADING_WEIGHT * self.bm25_heading.scores(q_toks)
        bm_order = np.argsort(-bm)
        if self.embeddings is None or self.embed is None:
            return [Hit(self.chunks[i], float(bm[i]), r) for r, i in enumerate(bm_order[:k]) if bm[i] > 0]

        q_vec = _normalise(self.embed([query]))[0]
        dense = self.embeddings @ q_vec
        dense_order = np.argsort(-dense)
        fused = np.zeros(len(self.chunks))
        for r, i in enumerate(bm_order):
            if bm[i] > 0:
                fused[i] += 1 / (rrf_k + r + 1)
        for r, i in enumerate(dense_order):
            fused[i] += 1 / (rrf_k + r + 1)
        order = np.argsort(-fused)[:k]
        # Report the BM25 score for thresholding decisions; dense-only matches get 0.
        return [Hit(self.chunks[i], float(bm[i]), r) for r, i in enumerate(order)]

    # Persistence -----------------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"chunks": [asdict(c) for c in self.chunks]}, ensure_ascii=False))
        if self.embeddings is not None:
            np.save(path.with_suffix(".npy"), self.embeddings)

    @classmethod
    def load(cls, path: Path, embed: Callable[[list[str]], np.ndarray] | None = None) -> Index:
        data = json.loads(path.read_text())
        chunks = [Chunk(**c) for c in data["chunks"]]
        emb_path = path.with_suffix(".npy")
        embeddings = np.load(emb_path) if (embed is not None and emb_path.exists()) else None
        return cls(chunks, embed=embed, embeddings=embeddings)


def _normalise(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=float)
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-9, None)
