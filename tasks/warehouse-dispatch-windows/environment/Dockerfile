FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep bash curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# A build-time startup check keeps Harbor from needing an installer during a trial.
ARG TARGETARCH
RUN set -eu; \
    case "$TARGETARCH" in \
      arm64) \
        npm_arch=arm64; rust_arch=aarch64; \
        cli_digest=8a96f66d059d653e68bfd5f3c79337e6f1d7d170d80bf705eb7d0249b34c0ece; \
        host_digest=255eccc8a5c1d267dc0acbc815cc83aaa1f50955bd99943b29f00cafcdcab771 ;; \
      amd64) \
        npm_arch=x64; rust_arch=x86_64; \
        cli_digest=399ff69c431c066e40de318fba45c2b07f45a76b19939d247ee4828fc70c4215; \
        host_digest=8724d73ec190536233ab4628d24a071bfbcf27e5124f08fe35129f26fe48b916 ;; \
      *) echo "Unsupported Codex architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    curl --fail --silent --show-error --retry 2 --max-time 90 \
      "https://registry.npmjs.org/@openai/codex/-/codex-0.163.0-linux-$npm_arch.tgz" \
      -o /tmp/codex.tgz; \
    prefix="package/vendor/${rust_arch}-unknown-linux-musl/bin"; \
    tar -xzf /tmp/codex.tgz -C /usr/local/bin --strip-components=4 \
      "$prefix/codex" "$prefix/codex-code-mode-host"; \
    rm /tmp/codex.tgz; \
    printf '%s  %s\n' "$cli_digest" /usr/local/bin/codex \
      "$host_digest" /usr/local/bin/codex-code-mode-host | sha256sum -c -; \
    chmod 755 /usr/local/bin/codex /usr/local/bin/codex-code-mode-host; \
    test "$(codex --version)" = 'codex-cli 0.163.0'; \
    codex-code-mode-host </dev/null

ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY workspace/ /app/
