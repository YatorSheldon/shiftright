"""Pluggable answer generators.

- ``ollama``     (default) a local model through Ollama's HTTP API. Free, private.
- ``anthropic``  Claude, via the ``anthropic`` SDK and ANTHROPIC_API_KEY.
- ``openai``     via the ``openai`` SDK and OPENAI_API_KEY.
- ``extractive`` no model at all: returns the most relevant source sentences.
                 Used in tests, CI and demos where no model is available.

Choose with SHIFTRIGHT_LLM, and the model with SHIFTRIGHT_MODEL. Hybrid search embeddings
come from fastembed (default) or Ollama, chosen with SHIFTRIGHT_EMBEDDER.
"""

from __future__ import annotations

import os
import re
from typing import Protocol

import numpy as np
import requests


class LLM(Protocol):
    name: str

    def generate(self, system: str, prompt: str) -> str: ...


class OllamaLLM:
    def __init__(self, model: str | None = None, host: str | None = None, timeout: float = 120):
        self.model = model or os.getenv("SHIFTRIGHT_MODEL", "llama3.2:3b")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout
        self.name = f"ollama:{self.model}"

    def generate(self, system: str, prompt: str) -> str:
        resp = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "options": {"temperature": 0.1},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class AnthropicLLM:
    def __init__(self, model: str | None = None):
        import anthropic  # optional dependency

        self.client = anthropic.Anthropic()
        self.model = model or os.getenv("SHIFTRIGHT_MODEL", "claude-haiku-5-5")
        self.name = f"anthropic:{self.model}"

    def generate(self, system: str, prompt: str) -> str:
        msg = self.client.messages.create(
            model=self.model, max_tokens=800, temperature=0.1, system=system, messages=[{"role": "user", "content": prompt}]
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


class OpenAILLM:
    def __init__(self, model: str | None = None):
        from openai import OpenAI  # optional dependency

        self.client = OpenAI()
        self.model = model or os.getenv("SHIFTRIGHT_MODEL", "gpt-4o-mini")
        self.name = f"openai:{self.model}"

    def generate(self, system: str, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0.1, messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content or ""


class ExtractiveLLM:
    """Model-free fallback: picks the source sentences that best match the question."""

    name = "extractive"

    def generate(self, system: str, prompt: str) -> str:
        from shiftright.index import tokenize

        question = prompt.split("QUESTION:", 1)[-1].strip()
        q = set(tokenize(question))
        scored = []
        for m in re.finditer(r"^\[(\d+)\][^\n]*\n(.*?)(?=\n\[\d+\] |\nQUESTION:|\Z)", prompt, flags=re.DOTALL | re.MULTILINE):
            num, body = m.group(1), m.group(2)
            for sent in re.split(r"(?<=[.;:])\s+", body.strip()):
                overlap = len(q & set(tokenize(sent)))
                if overlap and len(sent.split()) >= 6:
                    scored.append((overlap, -len(scored), sent.strip(), num))
        if not scored:
            return "NOT_COVERED"
        best = sorted(scored, reverse=True)[:3]
        return " ".join(f"{s} [{n}]" for _, _, s, n in best)


def get_llm(kind: str | None = None) -> LLM:
    kind = (kind or os.getenv("SHIFTRIGHT_LLM", "ollama")).lower()
    if kind == "ollama":
        return OllamaLLM()
    if kind == "anthropic":
        return AnthropicLLM()
    if kind == "openai":
        return OpenAILLM()
    if kind == "extractive":
        return ExtractiveLLM()
    raise ValueError(f"Unknown SHIFTRIGHT_LLM '{kind}'. Use ollama, anthropic, openai or extractive.")


def fastembed_embedder(model: str | None = None):
    """Local CPU embeddings via fastembed (ONNX; no GPU or server needed). ``pip install fastembed``."""
    from fastembed import TextEmbedding  # optional dependency

    encoder = TextEmbedding(model_name=model or os.getenv("SHIFTRIGHT_EMBED_MODEL", "BAAI/bge-small-en-v1.5"))

    def embed(texts: list[str]) -> np.ndarray:
        return np.array(list(encoder.embed(texts, batch_size=64)), dtype=float)

    return embed


def get_embedder(kind: str | None = None):
    """Embedding backend for hybrid search: ``fastembed`` (default) or ``ollama``."""
    kind = (kind or os.getenv("SHIFTRIGHT_EMBEDDER", "fastembed")).lower()
    if kind == "fastembed":
        return fastembed_embedder()
    if kind == "ollama":
        return ollama_embedder()
    raise ValueError(f"Unknown SHIFTRIGHT_EMBEDDER '{kind}'. Use fastembed or ollama.")


def ollama_embedder(model: str | None = None, host: str | None = None):
    """Return an embedding function backed by Ollama, for hybrid search."""
    model = model or os.getenv("SHIFTRIGHT_EMBED_MODEL", "nomic-embed-text")
    host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")

    def embed(texts: list[str]) -> np.ndarray:
        vecs = []
        for i in range(0, len(texts), 32):
            resp = requests.post(f"{host}/api/embed", json={"model": model, "input": texts[i : i + 32]}, timeout=120)
            resp.raise_for_status()
            vecs.extend(resp.json()["embeddings"])
        return np.array(vecs, dtype=float)

    return embed
