#!/usr/bin/env bash
set -euo pipefail
mkdir -p submission
clang-14 --target=wasm32-wasi --sysroot=/usr -O2 -nostartfiles \
  -Wl,--no-entry -Wl,--export=solve -Wl,--export=__heap_base \
  -Wl,--stack-first -Wl,-z,stack-size=65536 \
  -Wl,--initial-memory=1572864 -Wl,--max-memory=1572864 \
  -I/app "${1:-kernel.c}" -lm -o submission/kernel.wasm
