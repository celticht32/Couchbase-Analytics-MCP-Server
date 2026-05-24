# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT

PY ?= python3
VENV ?= .venv
ACT = . $(VENV)/bin/activate

.PHONY: help venv install dev run gui test test-unit test-integration \
        coverage scan pyflakes ruff mypy bandit clean screenshots docker

help:
	@echo "Targets:"
	@echo "  venv              Create virtualenv at $(VENV)"
	@echo "  install           Install runtime dependencies"
	@echo "  dev               Install runtime + dev dependencies"
	@echo "  run               Run the MCP server + GUI (default port 8000/8080)"
	@echo "  gui               Run only the GUI (without MCP server)"
	@echo "  test              Run unit tests"
	@echo "  test-integration  Run integration tests (requires Playwright)"
	@echo "  coverage          Run tests with coverage report"
	@echo "  scan              Run deep scan (pyflakes + ruff + mypy + bandit + tests)"
	@echo "  pyflakes          Run pyflakes only"
	@echo "  ruff              Run ruff lint only"
	@echo "  mypy              Run mypy only"
	@echo "  bandit            Run bandit security scan only"
	@echo "  screenshots       Generate GUI screenshots via headless Playwright"
	@echo "  docker            Build the Docker image"
	@echo "  clean             Remove build artefacts and caches"

venv:
	$(PY) -m venv $(VENV)
	$(ACT) && pip install -U pip wheel

install: venv
	$(ACT) && pip install -e .

dev: venv
	$(ACT) && pip install -e ".[dev]"

run:
	$(ACT) && cb-analytics-mcp

gui:
	$(ACT) && $(PY) -m cb_analytics_mcp --gui-only

test:
	$(ACT) && pytest tests/unit -v

test-integration:
	$(ACT) && pytest tests/integration -v -m integration

coverage:
	$(ACT) && pytest tests/unit --cov --cov-report=term-missing --cov-report=html --cov-fail-under=80

# ── Deep scan ──────────────────────────────────────────────────────────────────

scan: pyflakes ruff mypy bandit test
	@echo ""
	@echo "✓ All scans clean."

pyflakes:
	$(ACT) && pyflakes src

ruff:
	$(ACT) && ruff check src tests

mypy:
	$(ACT) && mypy src

bandit:
	$(ACT) && bandit -r src -c pyproject.toml

# ── Docs & screenshots ─────────────────────────────────────────────────────────

screenshots:
	$(ACT) && playwright install chromium
	$(ACT) && $(PY) scripts/make_screenshots.py

# ── Docker ─────────────────────────────────────────────────────────────────────

docker:
	docker build -t cb-analytics-mcp:latest .

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
