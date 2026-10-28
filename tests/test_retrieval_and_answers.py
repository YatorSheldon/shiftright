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
    assert index.search("what makes someone a casual", k=3)[0].chunk.number == "10"
    assert index.search("does my boss have to give me a payslip", k=3)[0].chunk.number == "30"
    assert index.search("unused annual leave when my job ends", k=3)[0].chunk.number == "21"


def test_hybrid_search_uses_embeddings(pages):
    from shiftright.chunk import chunk_pages

    chunks = chunk_pages(pages)
    target = next(i for i, c in enumerate(chunks) if c.number == "30")

    def embed(texts):  # toy embedder: the query and the pay-slip section point the same way
        return np.array([[1.0, 0.0] if ("pay slip" in t.lower() or "wage statement" in t.lower()) else [0.0, 1.0] for t in texts])

    idx = Index(chunks, embed=embed)
    hits = idx.search("wage statement", k=3)  # no keyword overlap: only the dense side can find it
    assert hits[0].chunk is chunks[target]


def test_answer_has_valid_citations_only(index):
    llm = FakeLLM("A casual has no firm commitment to ongoing work (s 10) [1]. Something unsupported [9].")
    ans = answer_question("What makes someone a casual employee?", index, llm, min_score=0.1)
    assert ans.covered
    assert "[1]" in ans.text and "[9]" not in ans.text
    assert [s.number for s in ans.sources] == [1]
    assert ans.sources[0].section == "10" and ans.sources[0].url.endswith("#s10")
    assert "QUESTION: What makes someone a casual employee?" in llm.prompts[0]


def test_uncited_answer_is_not_shown(index):
    ans = answer_question("What makes someone a casual employee?", index, FakeLLM("Yes, definitely."), min_score=0.1)
    assert not ans.covered


def test_model_refusal_and_low_score_refusal(index):
    assert not answer_question("casual employee meaning", index, FakeLLM("NOT_COVERED"), min_score=0.1).covered
    llm = FakeLLM("should never be called [1]")
    ans = answer_question("How do I renew my passport?", index, llm)
    assert not ans.covered and llm.prompts == []  # retrieval score too low, model never asked


def test_extractive_fallback_cites_sources(index):
    ans = answer_question("Does my employer have to give me a pay slip?", index, ExtractiveLLM(), min_score=0.1)
    assert ans.covered
    assert any(s.section == "30" for s in ans.sources)


def test_prompt_numbers_sources(index):
    prompt = build_prompt("q", index.search("annual leave", k=2))
    assert prompt.startswith("SOURCES:\n[1] ") and "\n[2] " in prompt


def test_api_ask_and_validation(index, monkeypatch):
    from shiftright import api

    monkeypatch.setattr(api, "_index", lambda: index)
    monkeypatch.setattr(api, "_llm", lambda: ExtractiveLLM())
    monkeypatch.setattr(api, "MIN_SCORE", 0.1)
    client = TestClient(api.app)
    assert client.get("/health").json()["status"] == "ok"
    body = client.post("/ask", json={"question": "What happens to untaken annual leave when employment ends?"}).json()
    assert body["covered"] and body["sources"] and "not legal advice" in body["disclaimer"]
    assert client.post("/ask", json={"question": "hi"}).status_code == 422


def test_payslip_matches_the_acts_two_word_spelling():
    assert tokenize("my payslip") == tokenize("my pay slip")


def test_non_work_questions_are_refused_before_search(index):
    from shiftright.answer import is_work_question

    assert not is_work_question("How do I renew my Australian passport?")
    assert is_work_question("Can my boss make me work on Christmas Day?")
    llm = FakeLLM("should never be called [1]")
    assert not answer_question("What's a good pasta recipe?", index, llm, min_score=0.0).covered
    assert llm.prompts == []
