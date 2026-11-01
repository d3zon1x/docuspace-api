# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system --gid 10001 appgroup \
    && useradd --system --uid 10001 --gid appgroup --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup src ./src

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
