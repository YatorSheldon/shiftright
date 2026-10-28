"""Command line: ``python -m shiftright.cli ingest | ask | eval``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from shiftright.answer import DISCLAIMER, answer_question
from shiftright.chunk import chunk_pages
from shiftright.fetch import fetch_all, load_pages
from shiftright.index import Index
from shiftright.llm import get_llm, ollama_embedder

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv("SHIFTRIGHT_DATA", ROOT / "data"))
RAW_DIR = DATA / "raw"
INDEX_PATH = DATA / "index.json"


def _embedder(enabled: bool):
    return ollama_embedder() if enabled else None


def cmd_ingest(args) -> int:
    if not args.skip_fetch:
        saved = fetch_all(RAW_DIR, refresh=args.refresh, delay_s=args.delay)
        print(f"{len(saved)} pages on disk.")
    pages = load_pages(RAW_DIR)
    if not pages:
        print("No pages found. Run without --skip-fetch first.", file=sys.stderr)
        return 1
    chunks = chunk_pages(pages)
    index = Index(chunks, embed=_embedder(args.embeddings))
    index.save(INDEX_PATH)
    print(f"Indexed {len(chunks)} passages from {len(pages)} pages{' with embeddings' if args.embeddings else ''} -> {INDEX_PATH}")
    return 0


def load_index(embeddings: bool = False) -> Index:
    if not INDEX_PATH.exists():
        raise SystemExit("No index yet. Run: python -m shiftright.cli ingest")
    return Index.load(INDEX_PATH, embed=_embedder(embeddings))


def cmd_ask(args) -> int:
    ans = answer_question(" ".join(args.question), load_index(args.embeddings), get_llm(args.llm))
    print(ans.text)
    for s in ans.sources:
        print(f"  [{s.number}] {s.title} > {s.heading}\n      {s.url}")
    print(f"\n{DISCLAIMER}  (model: {ans.model})")
    return 0


def cmd_eval(args) -> int:
    from shiftright.evaluate import evaluate, load_questions

    llm = get_llm(args.llm) if args.llm else None
    report = evaluate(load_index(args.embeddings), load_questions(Path(args.questions)), llm=llm)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "misses"}, indent=2))
    if report["misses"]:
        print(f"\n{len(report['misses'])} retrieval misses (see {out})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="shiftright", description="Australian workplace-rights assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="download guidance pages and build the search index")
    pi.add_argument("--refresh", action="store_true", help="re-download pages already on disk")
    pi.add_argument("--skip-fetch", action="store_true", help="only rebuild the index from pages on disk")
    pi.add_argument("--embeddings", action="store_true", help="also embed passages with Ollama for hybrid search")
    pi.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    pi.set_defaults(func=cmd_ingest)

    pa = sub.add_parser("ask", help="ask a question")
    pa.add_argument("question", nargs="+")
    pa.add_argument("--llm", help="ollama | anthropic | openai | extractive")
    pa.add_argument("--embeddings", action="store_true")
    pa.set_defaults(func=cmd_ask)

    pe = sub.add_parser("eval", help="run the retrieval and refusal evaluation")
    pe.add_argument("--questions", default=str(ROOT / "eval" / "questions.jsonl"))
    pe.add_argument("--out", default=str(ROOT / "reports" / "eval.json"))
    pe.add_argument("--llm", help="defaults to extractive (no model needed)")
    pe.add_argument("--embeddings", action="store_true")
    pe.set_defaults(func=cmd_eval)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
