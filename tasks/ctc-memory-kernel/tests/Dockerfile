FROM python:3.12.14-slim-bookworm
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /grader
COPY ctcbench/ /grader/ctcbench/
COPY private.npz /grader/private.npz
COPY test.sh /tests/test.sh
