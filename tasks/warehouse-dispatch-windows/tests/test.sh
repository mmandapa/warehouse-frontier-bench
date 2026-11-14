#!/usr/bin/env bash
set -euo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier
WAREHOUSE_ISOLATE_CASES=1 python3 -B /grader/grade.py --policy /app/policy.py --logs /logs/verifier
