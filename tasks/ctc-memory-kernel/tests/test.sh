#!/usr/bin/env bash
set -euo pipefail
cd /grader
export PYTHONPATH=/grader
python -m ctcbench.grade --logs /logs/verifier
