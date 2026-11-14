FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
RUN useradd --uid 1001 --create-home candidate && mkdir -p /logs/verifier
RUN set -eux; \
    runtime=/opt/warehouse-python; \
    mkdir -p "$runtime/usr/local/bin" "$runtime/usr/local/lib" "$runtime/usr/lib" /opt/warehouse-cases; \
    cp -a /usr/local/bin/python3.12 "$runtime/usr/local/bin/"; \
    cp -a /usr/local/lib/libpython3.12.so.1.0 /usr/local/lib/python3.12 "$runtime/usr/local/lib/"; \
    cp -a /usr/lib/*-linux-gnu "$runtime/usr/lib/"; \
    ln -s usr/lib "$runtime/lib"; \
    loader="$(ldd /usr/local/bin/python3.12 | awk '$1 ~ /^\// && $2 ~ /^\(/ {print $1}')"; \
    test -n "$loader"; \
    install -D -m 755 "$(readlink -f "$loader")" "$runtime$loader"; \
    find "$runtime" -type f -exec chmod a-s,go-w {} +; \
    LD_LIBRARY_PATH=/usr/local/lib chroot --userspec=1001:1001 "$runtime" /usr/local/bin/python3.12 -B -c 'import ctypes, math, sqlite3, ssl, zlib'
ENV PYTHONDONTWRITEBYTECODE=1
COPY grader/ /grader/
COPY test.sh /tests/test.sh
RUN chmod 700 /grader /logs/verifier
WORKDIR /
