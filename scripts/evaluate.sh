#!/usr/bin/env bash
# Build the index from the live guidance pages and run the evaluation.
# Run this on your own machine: the guidance site does not respond to cloud CI servers.
# Writes metrics only (no page text) to reports/eval.json, which is safe to commit.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
python -m shiftright.cli ingest "$@"
python -m shiftright.cli eval
