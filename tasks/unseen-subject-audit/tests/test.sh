#!/usr/bin/env bash
set -euo pipefail
cd /grader
export PYTHONPATH=/grader
python -m rrbench.verifier
