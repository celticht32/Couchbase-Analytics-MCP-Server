# Contributing to cb-analytics

Copyright © 2026 Chris Ahrendt. All contributions are welcome under the MIT License.

## Development Setup

```bash
git clone https://github.com/celticht32/Couchbase-Analytics-MCP-Server.git
cd Couchbase-Analytics-MCP-Server
pip install -e ".[dev]"
pre-commit install
```

## Running Tests

```bash
# Unit tests (no Couchbase required)
make test

# With coverage
make coverage

# Integration tests (requires running Couchbase)
docker-compose up -d
CB_ANALYTICS_HOST=localhost pytest tests/integration/ -v
```

## Code Standards

- **Formatting**: ruff (line length 100)
- **Types**: mypy strict mode — all public functions must be typed
- **Imports**: no unused imports — pyflakes must report zero warnings
- **Security**: bandit must report zero medium/high issues
- **Tests**: new features require unit tests; coverage must stay ≥ 95%
- **Secrets**: never use plain `str` for passwords/tokens — use `SecretStr`

Run all checks: `make all`

## Pull Request Process

1. Fork the repository and create a feature branch
2. Write tests for your changes
3. Ensure `make all` passes with zero errors
4. Update `CHANGELOG.md` under the `[Unreleased]` section
5. Submit a PR with a clear description of the change and its motivation

## Commit Message Format

```
type(scope): short description

Longer explanation if needed.

Fixes #issue-number
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`

## Adding a New API Endpoint

1. Add the model(s) to `src/cb_analytics/models/__init__.py`
2. Add the method to the appropriate API class in `src/cb_analytics/api/`
3. Add unit tests in `tests/unit/test_<api>_api.py`
4. Update `docs/architecture/ARCHITECTURE.md` endpoint tables
5. Update `CHANGELOG.md`
