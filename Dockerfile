# ── Stage 1: build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml README.md ./
COPY . .

# Install dependencies into a virtual environment
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install the base package. Add optional extras here if needed (e.g. .[web,gemini])
RUN uv pip install --no-cache .

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN useradd --create-home --shell /bin/bash axon
WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder --chown=axon:axon /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY --chown=axon:axon . .

# Ensure data directory exists and is owned by axon for SQLite/Turso
RUN mkdir -p /data && chown -R axon:axon /data

USER axon

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Default command
CMD ["granian", "--interface", "asgi", "app:app", "--host", "0.0.0.0", "--port", "8080"]
