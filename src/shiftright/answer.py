"""Question -> retrieved passages -> grounded answer with checked citations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from shiftright.index import Hit, Index
from shiftright.llm import LLM
from shiftright.sources import LICENCE_NAME, REGISTER_URL

SYSTEM_PROMPT = """You explain Australian workplace law to students and young workers in plain English.

The numbered sources are sections of the Fair Work Act 2009 and the Fair Work Regulations 2009.

Rules:
- Use ONLY the numbered sources provided. Do not use outside knowledge.
- After every claim, cite the source number in square brackets, like [2].
- Translate legal wording into everyday language; mention the section number once, e.g. "(s 87)".
- If the sources do not answer the question, reply exactly: NOT_COVERED
- Do not state dollar amounts, rates or percentages unless a source states them.
- Pay rates and many conditions come from awards and agreements, which you don't have. If that matters, say so.
- Be concise: at most 6 sentences.
- You are not a lawyer and this is general information, not legal advice."""

NOT_COVERED_MESSAGE = (
    "I couldn't find this in the Fair Work Act or Regulations. It may depend on your award or agreement. "
    "The Fair Work Ombudsman (fairwork.gov.au, 13 13 94) can help with your situation."
)
DISCLAIMER = "General information only, not legal advice. Your award or agreement may give you more."

# Minimum keyword score of the best passage before we even ask the model.
MIN_SCORE = 2.0

# A question must mention something about work before we search the law for it.
# Keyword scores alone can't tell "renew my passport" (which shares words like "renew"
# with the Act) from a real workplace question, so this cheap check runs first.
WORK_ROOTS = (
    "employ",
    "work",
    "job",
    "boss",
    "pay",
    "paid",
    "wage",
    "salar",
    "leave",
    "holiday",
    "shift",
    "roster",
    "casual",
    "permanent",
    "part-time",
    "full-time",
    "award",
    "agreement",
    "contract",
    "dismiss",
    "sack",
    "fire",
    "redundan",
    "notice",
    "resign",
    "terminat",
    "hour",
    "overtime",
    "super",
    "union",
    "bull",
    "harass",
    "discriminat",
    "slip",
    "sick",
    "carer",
    "parental",
    "maternity",
    "paternity",
    "jury",
    "intern",
    "probation",
    "deduct",
    "uniform",
    "disconnect",
    "flexib",
    "colleague",
    "manager",
    "unfair",
    "ombudsman",
    "standards",
    "fair work",
    "stand down",
    "staff",
    "trial",
)


def is_work_question(question: str) -> bool:
    q = question.lower()
    return any(root in q for root in WORK_ROOTS)


@dataclass
class Source:
    number: int
    title: str
    heading: str
    url: str
    section: str = ""


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
            "source": f"Federal Register of Legislation ({REGISTER_URL}), {LICENCE_NAME}",
        }


def build_prompt(question: str, hits: list[Hit]) -> str:
    parts = []
    for n, h in enumerate(hits, 1):
        c = h.chunk
        parts.append(f"[{n}] {c.page_title} {c.heading} ({c.context})\n{c.text}")
    return "SOURCES:\n" + "\n".join(parts) + f"\nQUESTION: {question}"


def _cited_numbers(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\[(\d+)\]", text)]


def answer_question(question: str, index: Index, llm: LLM, k: int = 5, min_score: float = MIN_SCORE) -> Answer:
    question = question.strip()
    if not is_work_question(question):
        return Answer(question, NOT_COVERED_MESSAGE, covered=False, model=llm.name)
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
        Source(
            number=n,
            title=hits[n - 1].chunk.page_title,
            heading=hits[n - 1].chunk.heading,
            url=hits[n - 1].chunk.url,
            section=hits[n - 1].chunk.number,
        )
        for n in sorted(valid)
    ]
    return Answer(question, text, covered=True, sources=sources, model=llm.name, retrieved=hits)
