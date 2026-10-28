"""REST API.  Run:  uvicorn shiftright.api:app   (docs at /docs)"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shiftright import __version__
from shiftright.answer import MIN_SCORE, answer_question
from shiftright.llm import get_llm

app = FastAPI(title="ShiftRight API", version=__version__, description="Answers Australian workplace-rights questions with cited sources.")


class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, examples=["Do casual employees get paid sick leave?"])


@lru_cache(maxsize=1)
def _index():
    from shiftright.cli import load_index

    return load_index()


@lru_cache(maxsize=1)
def _llm():
    return get_llm()


@app.get("/health")
def health() -> dict:
    try:
        idx = _index()
    except SystemExit:
        return {"status": "no_index"}
    return {"status": "ok", "passages": len(idx.chunks), "llm": _llm().name}


@app.post("/ask")
def ask(q: Question) -> dict:
    try:
        idx = _index()
    except SystemExit as exc:
        raise HTTPException(status_code=503, detail="Index not built. Run the ingest command first.") from exc
    try:
        return answer_question(q.question, idx, _llm(), min_score=MIN_SCORE).to_dict()
    except Exception as exc:  # model server down, bad key, etc.
        raise HTTPException(status_code=502, detail=f"The language model didn't respond: {exc}") from exc
