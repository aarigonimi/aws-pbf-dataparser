# syntax=docker/dockerfile:1

# TODO: Pin both Python base images by digest once the desired linux/amd64
# digests can be resolved and recorded. Registry access was unavailable here.
ARG PYTHON_BASE=python:3.12-slim

# Build wheels in a disposable stage so the runtime image stays small.
FROM ${PYTHON_BASE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        libosmium2-dev \
        libexpat1-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM ${PYTHON_BASE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libexpat1 \
        zlib1g \
        libbz2-1.0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app
COPY requirements.txt ./
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=app:app src ./src

USER app
STOPSIGNAL SIGTERM

# src/main.py installs SIGTERM/SIGINT handlers and exits cleanly so AWS Batch
# can retry interrupted jobs when Batch reports a retryable host failure.
ENTRYPOINT ["python", "-m", "src.main"]
