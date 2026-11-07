#!/usr/bin/env bash
set -euo pipefail
cd /app
export PYTHONPATH=/app
python /solution/network_probe.py
python /solution/solve.py
