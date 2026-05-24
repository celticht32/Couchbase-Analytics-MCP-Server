# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT

# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build wheels for all dependencies into /wheels
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --upgrade pip wheel \
    && pip wheel --wheel-dir=/wheels .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Run as a non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /bin/bash app

WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-index --find-links=/wheels cb-analytics-mcp \
    && rm -rf /wheels

# Mount points for runtime artefacts
RUN mkdir -p /var/lib/cb-analytics-mcp /etc/cb-analytics-mcp \
    && chown -R app:app /var/lib/cb-analytics-mcp /etc/cb-analytics-mcp /app

USER app

EXPOSE 8000 8080 9100

# Sensible defaults for in-container audit + log paths.
ENV AUDIT_LOG_FILE=/var/lib/cb-analytics-mcp/audit.log \
    LOG_FORMAT=json \
    GUI_HOST=0.0.0.0 \
    MCP_HOST=0.0.0.0

# Health check uses the GUI's /healthz endpoint (unauthenticated, fast,
# 200 if the process is up). Switch to /readyz if you want failed clusters
# to fail the health check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
                   sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz', timeout=3).status == 200 else 1)"

ENTRYPOINT ["cb-analytics-mcp"]
