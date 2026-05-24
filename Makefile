# Copyright (c) 2026 Chris Ahrendt — MIT License
.PHONY: install test lint typecheck coverage clean docs security all

install:
	pip install -e ".[dev]"

test:
	pytest tests/unit/ -v --no-cov

coverage:
	pytest tests/unit/ --cov=cb_analytics --cov-report=html --cov-report=term-missing
	@echo "Open htmlcov/index.html to view coverage report"

integration:
	pytest tests/integration/ -v --no-cov

lint:
	ruff check src/ tests/
	python -m pyflakes src/cb_analytics/

typecheck:
	mypy src/cb_analytics/ --ignore-missing-imports

security:
	bandit -r src/cb_analytics/ -ll

docs:
	cd docs && node build_doc.js

clean:
	rm -rf htmlcov/ .coverage dist/ build/ src/*.egg-info/ __pycache__ .mypy_cache .ruff_cache
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

all: lint typecheck security coverage
	@echo "All checks passed."
