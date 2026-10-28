# ShiftRight: workplace-rights answers with receipts

![CI](https://github.com/YatorSheldon/shiftright/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/code-MIT-green)

A retrieval-augmented generation (RAG) assistant that answers Australian workplace-rights questions
(casual pay, unpaid trials, leave, rosters, final pay) from official public guidance, and **cites the
exact page behind every sentence**. It runs free and private on a laptop with a local model through
Ollama, and can switch to Claude or OpenAI with one environment variable.

> Ask: *"Is an unpaid trial shift legal?"*
> Get: a short answer, numbered citations, and links to the guidance pages it used. Or, when the
> guidance doesn't cover the question, an honest "I couldn't find this" instead of a guess.

## Why

Students and young workers are some of the most likely people to be underpaid, and the answers to
their questions are public but spread across dozens of pages. A general chatbot will happily
answer from memory, including out-of-date or made-up rules. ShiftRight answers **only** from the
retrieved guidance, shows its sources, and declines when it can't support an answer.

## How it works

```
fetch (your machine) ──► clean + split into sections ──► passages with page + heading
        │                                                         │
        ▼                                                         ▼
   robots.txt, 1.5 s delay,                      BM25 keyword index  (+ optional Ollama embeddings,
   identifies itself                             fused with reciprocal rank fusion)
                                                                  │
question ──► top-5 passages ──► score too low? ──► "not covered" (model never called)
                                    │
                                    ▼
                    numbered sources + strict prompt ──► LLM ──► citation check ──► answer + links
```

| Stage | Design choice | Why |
| --- | --- | --- |
| Ingest | [`fetch.py`](src/shiftright/fetch.py) downloads ~50 pages on *your* machine | Keeps the repo free of copied content; easy to refresh when guidance changes |
| Chunking | Section-aware, ~160 words, 30-word overlap, page title and heading kept on every passage | A passage about "casual loading" still says where it came from |
| Retrieval | BM25 written from scratch, Australian slang folded in ("sacked" → dismissed, "sickie" → sick), optional dense embeddings | Works with zero model downloads; hybrid search when Ollama is available |
| Guardrails | Score threshold before generation; the model must cite; uncited or out-of-range citations are stripped or the answer is withheld | No unsupported answers reach the user |
| Generation | Pluggable: Ollama (default), Claude, OpenAI, or a model-free extractive mode | Free locally, better quality with an API key, testable in CI |

## Evaluation

[`eval/questions.jsonl`](eval/questions.jsonl) holds 34 realistic student questions, each labelled with
the page(s) that should answer it, plus 6 out-of-scope questions (passports, recipes, the weather)
that the assistant should decline. [`scripts/evaluate.sh`](scripts/evaluate.sh) downloads the live
pages, rebuilds the index and reports:

- **page hit@k**: share of questions whose correct page is in the top *k* results
- **MRR**: how high the first correct page ranks
- **refusal accuracy**: share of out-of-scope questions declined
- **false refusal rate**: share of answerable questions wrongly declined

The evaluation runs locally rather than in CI: the guidance site doesn't respond to requests from
cloud CI servers (found when the first CI evaluation timed out on every page). CI runs lint and the
unit tests on every push; the latest local metrics, numbers only, are in
[`reports/eval.json`](reports/eval.json).

## Run it

```bash
git clone https://github.com/YatorSheldon/shiftright.git && cd shiftright
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

PYTHONPATH=src python -m shiftright.cli ingest          # download pages + build index (~2 min)

# Option A: free and local with Ollama (https://ollama.com)
ollama pull llama3.2:3b
PYTHONPATH=src python -m shiftright.cli ask "Do casual workers get paid sick leave?"

# Option B: Claude or OpenAI
export SHIFTRIGHT_LLM=anthropic ANTHROPIC_API_KEY=...    # or SHIFTRIGHT_LLM=openai OPENAI_API_KEY=...

# Option C: no model at all (returns the best-matching source sentences)
PYTHONPATH=src python -m shiftright.cli ask --llm extractive "Is an unpaid trial shift legal?"

python app.py                                           # chat UI at http://localhost:7860
PYTHONPATH=src uvicorn shiftright.api:app               # REST API, docs at http://localhost:8000/docs
PYTHONPATH=src python -m shiftright.cli eval            # run the evaluation
```

Hybrid search: `ollama pull nomic-embed-text`, then add `--embeddings` to `ingest`, `ask` and `eval`.

## Project structure

```
src/shiftright/
  sources.py    the guidance pages covered, attribution and licence details
  fetch.py      polite downloader and HTML-to-sections parser
  chunk.py      section-aware chunking with overlap
  index.py      BM25 + optional embeddings, reciprocal rank fusion
  llm.py        Ollama / Claude / OpenAI / extractive providers
  answer.py     prompt, refusal threshold, citation checking
  evaluate.py   hit@k, MRR, refusal metrics
  cli.py        ingest | ask | eval
scripts/evaluate.sh   download pages, rebuild the index, run the evaluation
  api.py        FastAPI service
app.py          Gradio chat UI
tests/          parser, chunking, retrieval, guardrail and API tests (invented fixture text)
eval/           labelled evaluation questions
```

## Limitations

- Covers ~50 general guidance pages, not every award. Exact pay rates depend on your award or
  agreement, so answers point you to the pay guides rather than quoting rates from memory.
- Keyword retrieval can miss paraphrased questions. Hybrid search helps; the evaluation's miss list
  shows where.
- Small local models sometimes write clumsy answers. The citation check stops unsupported ones,
  but it can't make a weak answer elegant.

## Content licence and disclaimer

Answers draw on guidance pages **© Fair Work Ombudsman www.fairwork.gov.au**, used under the
[Creative Commons Attribution-NonCommercial 4.0 International licence](https://creativecommons.org/licenses/by-nc/4.0/legalcode).
Pages are downloaded on the user's machine at ingest time and split into passages for search;
wording is unchanged. This repository does not redistribute the pages. ShiftRight is a
non-commercial student project and is **not affiliated with or endorsed by** the Fair Work
Ombudsman or the Commonwealth. It gives general information, not legal advice. The code is MIT
licensed; the guidance content remains under its own licence.

---
Built by **Sheldon Kiprono**, Bachelor of Artificial Intelligence student at Deakin University.
