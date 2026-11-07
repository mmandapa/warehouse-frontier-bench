FROM node:22.20.0-bookworm-slim AS node
FROM python:3.12.14-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    apt-get update && apt-get install -y --no-install-recommends \
      bash curl ca-certificates git ripgrep clang-14 lld-14 wasi-libc libclang-rt-14-dev-wasm32 && \
    rm -rf /var/lib/apt/lists/* && npm install -g @openai/codex@0.163.0
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /app
COPY workspace/ /app/
