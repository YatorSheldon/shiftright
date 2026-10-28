# ShiftRight: workplace law, explained with receipts

![CI](https://github.com/YatorSheldon/shiftright/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/code-MIT-green)

A retrieval-augmented generation (RAG) assistant that answers Australian workplace questions from
the **Fair Work Act 2009** and **Fair Work Regulations 2009**, explains them in plain English, and
**cites the exact section behind every sentence**, with a deep link to it. It runs free and private
on a laptop, and can switch between a local model (Ollama), Claude or OpenAI with one environment
variable.

> **Q:** Does my employer have to give me a payslip?
> **A:** A short plain-English answer, citing **s 536** *Employer obligations in relation to pay slips*
> and **reg 3.46** *Pay slips: information to be included*, each linked to the section on the
> Federal Register of Legislation.
>
> **Q:** How do I renew my passport?
> **A:** *"I couldn't find this in the Fair Work Act or Regulations…"*, and the model is never called.

## Why

Students and young workers are some of the most likely people to be underpaid or to lose
entitlements they didn't know about. The rules are public, but they sit in a 1,700-section Act
written for lawyers. A general chatbot will answer from memory, including out-of-date rules.
ShiftRight answers **only** from the retrieved law, shows its sources, and declines when it can't
support an answer.

## How it works

```
Federal Register of Legislation ──► parse into numbered sections ──► 2,787 passages
  (robots.txt, 10 s crawl delay)     (s 87, reg 3.46, Part/Division)      │
                                                                          ▼
                                 BM25 (heading-weighted) + bge-small embeddings, fused (RRF)
                                                                          │
question ──► about work? ── no ──► "not covered"                          │
                │ yes                                                     │
                ▼                                                         │
           top-5 sections ◄───────────────────────────────────────────────┘
                │
                ▼
   numbered sources + strict prompt ──► LLM ──► citation check ──► answer + section links
```

| Stage | Design choice | Why |
| --- | --- | --- |
| Ingest | [`fetch.py`](src/shiftright/fetch.py) reads the Register's clean HTML and splits it on its section markup | Exact section numbers and deep links; one request per document, polite delays |
| Chunking | One passage per section, long sections split with overlap; Chapter/Part/Division kept on every passage | "s 87 Entitlement to annual leave" still says where it came from |
| Retrieval | BM25 written from scratch with heading weighting and everyday-word folding ("payslip" → "pay slip", "sacked" → dismissed), fused with dense embeddings | Keyword search nails exact terms; embeddings catch paraphrases like "tell my coworkers what I earn" → pay secrecy |
| Guardrails | Work-topic check, keyword-score floor, mandatory citations, out-of-range citations stripped, uncited answers withheld | No unsupported answer reaches the user |
| Generation | Pluggable: Ollama, Claude, OpenAI, or a model-free extractive mode | Free locally, better with an API key, testable without any model |

## Evaluation

Two labelled question sets, each question tagged with the section(s) that answer it:

- **Dev set:** 34 realistic questions + 6 off-topic ones. Used while improving the system.
- **Held-out set:** 15 + 4 more, [committed before any tuning](https://github.com/YatorSheldon/shiftright/commits/main/eval/holdout.jsonl) and run once at the end.

| Configuration | Set | Right section 1st | In top 3 | In top 5 | MRR | Off-topic refused | Real questions refused |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BM25 baseline | dev | 21% | 53% | 62% | 0.35 | 1 / 6 | 0% |
| BM25 + fixes below | dev | 38% | 68% | 68% | 0.50 | 6 / 6 | 0% |
| Hybrid (BM25 + embeddings) | dev | 56% | 74% | 82% | 0.66 | 6 / 6 | 0% |
| BM25 + fixes | **held-out** | 40% | 60% | 60% | 0.48 | 4 / 4 | 0% |
| **Hybrid** | **held-out** | **53%** | **60%** | **67%** | **0.57** | **4 / 4** | **0%** |

Raw numbers: [`reports/eval_summary.json`](reports/eval_summary.json).

**What moved the numbers, from reading the misses:**

1. **Schedule clauses were crowding out real rules.** The Act's Schedule 1 restarts its numbering
   (it has its own "clause 87"), and its transitional clauses about past amendments outranked the
   sections people ask about. Labelling them "Sch 1 cl 87" fixed a silent key collision; leaving
   them out of the index lifted results.
2. **Spelling mismatch.** People write "payslip", the Act writes "pay slip".
3. **Headings carry meaning.** Weighting a section's heading and Part/Division at 2× (a simple
   BM25F) helped questions whose answer is named in the title, like "Employee right to disconnect".
4. **Keyword scores can't do refusals.** "How do I renew my passport?" outscored several real
   questions, because the Act also talks about renewing things. A cheap "is this about work?"
   check before search fixed refusals without wrongly refusing any real question.
5. **Embeddings for paraphrase.** Hybrid search gave the biggest single jump.

**Honest limits of the evaluation:** the sets are small, so one question moves a score by 3–7
points. Some "misses" retrieve related, reasonable sections. For example, record-keeping questions
find the Regulations' detailed record rules rather than the Act's s 535. The held-out set is the
fairer estimate, and its gap from the dev set is the expected cost of tuning on dev.

## Run it

```bash
git clone https://github.com/YatorSheldon/shiftright.git && cd shiftright
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt fastembed

export PYTHONPATH=src                                     # Windows PowerShell: $env:PYTHONPATH="src"
python -m shiftright.cli ingest --embeddings              # download the law + build the index (~5 min)

python -m shiftright.cli ask --llm extractive "Do casual employees get paid sick leave?"   # no model needed

ollama pull llama3.2:3b && python -m shiftright.cli ask "Can I be fired for being off sick?"   # free local model
export SHIFTRIGHT_LLM=anthropic ANTHROPIC_API_KEY=...     # or SHIFTRIGHT_LLM=openai OPENAI_API_KEY=...

python app.py                                             # chat UI at http://localhost:7860
uvicorn shiftright.api:app                                # REST API, docs at http://localhost:8000/docs
python -m shiftright.cli eval --embeddings                # dev set
python -m shiftright.cli eval --embeddings --questions eval/holdout.jsonl --out reports/holdout.json
```

## Project structure

```
src/shiftright/
  sources.py    titles indexed, licence and attribution
  fetch.py      polite downloader and legislation HTML parser
  chunk.py      section-aware chunking with overlap
  index.py      BM25 (heading-weighted) + optional embeddings, reciprocal rank fusion
  llm.py        Ollama / Claude / OpenAI / extractive providers; fastembed / Ollama embedders
  answer.py     work-topic check, prompt, refusal threshold, citation checking
  evaluate.py   hit@k, MRR, refusal metrics
  cli.py        ingest | ask | eval
  api.py        FastAPI service
app.py          Gradio chat UI
tests/          parser, chunking, retrieval, guardrail and API tests (invented fixture text)
eval/           dev and held-out question sets
scripts/        evaluate.sh: download, index and run both evaluation sets
reports/        evaluation results (numbers only)
```

## Engineering notes

- **Why the corpus is the legislation.** The first version used the Fair Work Ombudsman's
  plain-English guidance. Its site doesn't respond to automated clients, from cloud CI or from a
  home connection, and disguising the downloader as a browser would mean evading its bot
  protection. The Federal Register of Legislation allows polite automated access and licenses its
  content more permissively, so ShiftRight explains the law itself.
- **A hang that taught me something.** Python's `urllib.robotparser.RobotFileParser.read()` has no
  timeout, so one silent server froze the first CI job. robots.txt is now fetched with a timeout,
  the downloader stops after repeated failures, and CI logs are unbuffered.
- CI runs lint and the unit tests on every push. The live-data evaluation runs locally, so CI never
  depends on a third-party site being up.

## Limitations

- Covers the Act and Regulations, not modern awards or enterprise agreements, which set most pay
  rates and many conditions. The assistant says so instead of guessing rates.
- Retrieval still misses some phrasings (see the held-out misses). Next steps: a reranker over the
  top 20, and query rewriting into legal vocabulary.
- Small local models can write clumsy answers. The citation check stops unsupported ones, but it
  can't make a weak answer elegant.

## Content licence and disclaimer

Based on content from the Federal Register of Legislation at 28 October 2026. For the latest
information on Australian Government legislation please go to https://www.legislation.gov.au.
Legislation content is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
ShiftRight downloads it on the user's machine and splits it into sections and passages for search.
This repository does not redistribute the legislation. ShiftRight is a student project, is not
affiliated with or endorsed by the Office of Parliamentary Counsel or the Commonwealth, and gives
general information, not legal advice. The code is MIT licensed.

---
Built by **Sheldon Kiprono**, Bachelor of Artificial Intelligence student at Deakin University.
