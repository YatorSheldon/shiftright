"""Question -> retrieved passages -> grounded answer with checked citations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from shiftright.index import Hit, Index
from shiftright.llm import LLM
from shiftright.sources import ATTRIBUTION

SYSTEM_PROMPT = """You answer questions about Australian workplace rights for students and young workers.

Rules:
- Use ONLY the numbered sources provided. Do not use outside knowledge.
- After every claim, cite the source number in square brackets, like [2].
- If the sources do not answer the question, reply exactly: NOT_COVERED
- Do not state specific dollar amounts or percentages unless a source states them.
- Be concise: at most 6 sentences, plain language, no legal jargon.
- You are not a lawyer and this is general information, not legal advice."""

NOT_COVERED_MESSAGE = (
    "I couldn't find this in the guidance I have. Try rephrasing, or contact the Fair Work Ombudsman directly "
    "(fairwork.gov.au) for help with your situation."
)
DISCLAIMER = "General information only, not legal advice. Check the linked pages for your award or agreement."

# Minimum BM25 score of the best passage before we even ask the model.
MIN_SCORE = 2.0


@dataclass
class Source:
    number: int
    title: str
    heading: str
    url: str


@dataclass
class Answer:
    question: str
    text: str
    covered: bool
    sources: list[Source] = field(default_factory=list)
    model: str = ""
    retrieved: list[Hit] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.text,
            "covered": self.covered,
            "sources": [s.__dict__ for s in self.sources],
            "model": self.model,
            "disclaimer": DISCLAIMER,
            "attribution": ATTRIBUTION,
        }


def build_prompt(question: str, hits: list[Hit]) -> str:
    parts = []
    for n, h in enumerate(hits, 1):
        c = h.chunk
        parts.append(f"[{n}] {c.page_title} > {c.heading} ({c.url})\n{c.text}")
    return "SOURCES:\n" + "\n".join(parts) + f"\nQUESTION: {question}"


def _cited_numbers(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\[(\d+)\]", text)]


def answer_question(question: str, index: Index, llm: LLM, k: int = 5, min_score: float = MIN_SCORE) -> Answer:
    question = question.strip()
    hits = index.search(question, k=k)
    if not hits or hits[0].score < min_score:
        return Answer(question, NOT_COVERED_MESSAGE, covered=False, model=llm.name, retrieved=hits)

    raw = llm.generate(SYSTEM_PROMPT, build_prompt(question, hits)).strip()
    if raw.upper().startswith("NOT_COVERED"):
        return Answer(question, NOT_COVERED_MESSAGE, covered=False, model=llm.name, retrieved=hits)

    # Keep only citations that point at sources we actually gave the model.
    valid = {n for n in _cited_numbers(raw) if 1 <= n <= len(hits)}
    text = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in valid else "", raw).strip()
    if not valid:
        # An uncited answer can't be checked, so we don't show it.
        return Answer(question, NOT_COVERED_MESSAGE, covered=False, model=llm.name, retrieved=hits)

    sources = [
        Source(number=n, title=hits[n - 1].chunk.page_title, heading=hits[n - 1].chunk.heading, url=hits[n - 1].chunk.url)
        for n in sorted(valid)
    ]
    return Answer(question, text, covered=True, sources=sources, model=llm.name, retrieved=hits)
