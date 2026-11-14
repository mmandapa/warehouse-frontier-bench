#!/usr/bin/env bash
set -euo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier
python3 -B /grader/grade.py --policy /app/policy.py --logs /logs/verifier
