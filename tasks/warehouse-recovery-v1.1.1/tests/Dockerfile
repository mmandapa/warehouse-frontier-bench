FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
RUN useradd --uid 1001 --create-home candidate && mkdir -p /logs/verifier
ENV PYTHONDONTWRITEBYTECODE=1
COPY grader/ /grader/
COPY test.sh /tests/test.sh
RUN chmod 700 /grader /logs/verifier
WORKDIR /
