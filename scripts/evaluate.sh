#!/usr/bin/env bash
# Download the legislation, build the hybrid index, and run both evaluation sets.
# Writes metrics and miss lists (no legislation text) to reports/.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
python -m shiftright.cli ingest --embeddings "$@"
python -m shiftright.cli eval --embeddings --out reports/dev_hybrid.json
python -m shiftright.cli eval --embeddings --questions eval/holdout.jsonl --out reports/holdout_hybrid.json
