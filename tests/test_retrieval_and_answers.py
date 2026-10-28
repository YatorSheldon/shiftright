import numpy as np
from fastapi.testclient import TestClient

from shiftright.answer import answer_question, build_prompt
from shiftright.index import Index, tokenize
from shiftright.llm import ExtractiveLLM


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.name, self.prompts = reply, "fake", []

    def generate(self, system, prompt):
        self.prompts.append(prompt)
        return self.reply


def test_tokenize_folds_slang_and_stopwords():
    assert tokenize("Can I get SACKED for a sickie?") == tokenize("dismissed sick") == ["dismiss", "sick"]


def test_bm25_ranks_the_right_page_first(index):
    assert index.search("do casuals get paid more per hour", k=3)[0].chunk.url.endswith("/casual-work")
    assert index.search("unpaid trial shift", k=3)[0].chunk.url.endswith("/unpaid-trials")
    assert index.search("unused annual leave when I resign", k=3)[0].chunk.url.endswith("/annual-leave")


def test_hybrid_search_uses_embeddings(pages):
    from shiftright.chunk import chunk_pages

    chunks = chunk_pages(pages)
    target = next(i for i, c in enumerate(chunks) if c.heading == "Internships")

    def embed(texts):  # toy embedder: the query and the internship chunk point the same way
        return np.array([[1.0, 0.0] if ("placement" in t.lower() or "internship" in t.lower()) else [0.0, 1.0] for t in texts])

    idx = Index(chunks, embed=embed)
    hits = idx.search("work placement", k=3)
    assert hits[0].chunk is chunks[target]


def test_answer_has_valid_citations_only(index):
    llm = FakeLLM("Casuals get a loading on top of the base rate [1]. Something unsupported [9].")
    ans = answer_question("Do casuals get paid more?", index, llm)
    assert ans.covered
    assert "[1]" in ans.text and "[9]" not in ans.text
    assert [s.number for s in ans.sources] == [1]
    assert ans.sources[0].url.endswith("/casual-work")
    assert "QUESTION: Do casuals get paid more?" in llm.prompts[0]


def test_uncited_answer_is_not_shown(index):
    ans = answer_question("Do casuals get paid more?", index, FakeLLM("Yes, definitely."))
    assert not ans.covered


def test_model_refusal_and_low_score_refusal(index):
    assert not answer_question("casual loading", index, FakeLLM("NOT_COVERED")).covered
    llm = FakeLLM("should never be called [1]")
    ans = answer_question("How do I renew my passport?", index, llm)
    assert not ans.covered and llm.prompts == []  # retrieval score too low, model never asked


def test_extractive_fallback_cites_sources(index):
    ans = answer_question("Is an unpaid trial shift allowed?", index, ExtractiveLLM())
    assert ans.covered
    assert any(s.url.endswith("/unpaid-trials") for s in ans.sources)


def test_prompt_numbers_sources(index):
    prompt = build_prompt("q", index.search("annual leave", k=2))
    assert prompt.startswith("SOURCES:\n[1] ") and "\n[2] " in prompt


def test_api_ask_and_validation(index, monkeypatch):
    from shiftright import api

    monkeypatch.setattr(api, "_index", lambda: index)
    monkeypatch.setattr(api, "_llm", lambda: ExtractiveLLM())
    client = TestClient(api.app)
    assert client.get("/health").json()["status"] == "ok"
    body = client.post("/ask", json={"question": "What happens to unused annual leave when I leave?"}).json()
    assert body["covered"] and body["sources"] and "not legal advice" in body["disclaimer"]
    assert client.post("/ask", json={"question": "hi"}).status_code == 422
