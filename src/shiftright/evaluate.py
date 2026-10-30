"""Retrieval and refusal evaluation.

Each line of ``eval/questions.jsonl`` is a question with the section(s) that
should answer it (``"FWA:87"`` = Fair Work Act 2009 s 87, ``"FWR:3.46"`` = Fair
Work Regulations 2009 reg 3.46), or ``"expect": "not_covered"`` for questions
the law doesn't answer. We measure:

- hit@k: share of answerable questions whose expected section is in the top k
- MRR:   mean reciprocal rank of the first expected section
- refusal accuracy: share of out-of-scope questions the pipeline declines,
  and share of answerable ones it does NOT decline (no false refusals)
"""

from __future__ import annotations

import json
from pathlib import Path

from shiftright.answer import answer_question
from shiftright.index import Index
from shiftright.llm import LLM, ExtractiveLLM

PREFIXES = {"FWA": "Fair Work Act 2009", "FWR": "Fair Work Regulations 2009"}


def section_key(ref: str) -> str:
    prefix, number = ref.split(":", 1)
    return f"{PREFIXES[prefix]}:{number}"


def load_questions(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(index: Index, questions: list[dict], k: int = 5, llm: LLM | None = None) -> dict:
    llm = llm or ExtractiveLLM()
    hits_at = {1: 0, 3: 0, 5: 0}
    rr_total = 0.0
    answerable = [q for q in questions if q.get("expect") != "not_covered"]
    out_of_scope = [q for q in questions if q.get("expect") == "not_covered"]
    misses = []

    for q in answerable:
        expected = {section_key(r) for r in q["sections"]}
        keys = []
        for h in index.search(q["question"], k=k * 3):
            if h.chunk.section_key not in keys:
                keys.append(h.chunk.section_key)
        keys = keys[:k]
        rank = next((i + 1 for i, key in enumerate(keys) if key in expected), None)
        for cut in hits_at:
            hits_at[cut] += int(rank is not None and rank <= cut)
        rr_total += 1 / rank if rank else 0.0
        if rank is None:
            misses.append({"question": q["question"], "expected": sorted(expected), "got": keys[:3]})

    false_refusals = sum(not answer_question(q["question"], index, llm).covered for q in answerable)
    correct_refusals = sum(not answer_question(q["question"], index, llm).covered for q in out_of_scope)

    n = max(len(answerable), 1)
    return {
        "answerable_questions": len(answerable),
        "out_of_scope_questions": len(out_of_scope),
        "page_hit@1": round(hits_at[1] / n, 3),
        "page_hit@3": round(hits_at[3] / n, 3),
        "page_hit@5": round(hits_at[5] / n, 3),
        "mrr": round(rr_total / n, 3),
        "refusal_accuracy_out_of_scope": round(correct_refusals / max(len(out_of_scope), 1), 3),
        "false_refusal_rate": round(false_refusals / n, 3),
        "llm": llm.name,
        "misses": misses,
    }
