# Contributing to cb-analytics-mcp

Thanks for considering a contribution. This project is small enough that
the workflow is short, but specific.

## Getting set up

```bash
git clone https://github.com/celticht32/cb-analytics-mcp
cd cb-analytics-mcp
make dev
```

That creates a `.venv/` and installs everything (runtime + dev) editably.

## Running the checks

One command runs every static check plus the full unit test suite:

```bash
make scan       # or: bash scripts/deep_scan.sh
```

Pass = your change is ready to push. If any of pyflakes, ruff, mypy
(strict), bandit, or pytest fails, the script exits non-zero and tells
you which one. Coverage must stay at or above 80 %.

You can run the individual scanners too:

```bash
make pyflakes
make ruff
make mypy
make bandit
make test
make coverage   # adds HTML report at htmlcov/
```

## Pull request expectations

- **Tests for new behaviour.** Tools have a paired `_impl()` that's easy to
  unit-test with `FakePool` — see `tests/unit/mcp/test_tool_impls.py` for
  the pattern. GUI routes use FastAPI's `TestClient` — see
  `tests/unit/gui/test_dashboard.py`.
- **`make scan` clean.** No exceptions; if a check is wrong, fix it or
  configure it, don't silence it.
- **Type annotations on new functions.** mypy is strict; untyped
  signatures will fail.
- **One change per PR.** Renames, refactors, and behaviour changes go
  separately so they review cleanly.
- **`CHANGELOG.md` entry** under `## [Unreleased]` for anything user-
  facing (new tool, new env var, GUI change, behaviour change).

## Code style

- `ruff format` is the source of truth — run `ruff format src tests`
  before committing.
- Line length 110 (set in `pyproject.toml`).
- Prefer small modules over large ones. Each MCP tool group is its own
  file; new groups should follow the same pattern.
- For new MCP tools, use the `_impl()` + `register()` split. The `_impl`
  is the testable unit; `register()` only wraps it with
  `call_tool_observed`.
- Secrets go through `pydantic.SecretStr` and the redactor sees them.
  Never log a raw secret.

## Adding a new MCP tool

1. Pick the right tool module (or create a new one matching the existing
   `tools/<group>.py` pattern).
2. Write the `<name>_impl()` function — async, takes the pool plus typed
   args, returns the result of `fmt_ok(...)`.
3. Add a `@mcp.tool()` wrapper in the module's `register()` function
   that calls `call_tool_observed(...)`.
4. Add unit tests in `tests/unit/mcp/test_tool_impls.py` (mock the pool,
   assert the right client method was called).
5. Update `docs/tool-reference.md` with the new tool's signature.
6. Update the matching skill in `.claude/skills/` if behaviour changes.
7. Add a `CHANGELOG.md` entry.

## Reporting bugs

Open a GitHub issue with:

- What you did (the exact tool call or steps).
- What you expected.
- What happened (with the relevant log line — keep the timestamp, redact
  secrets if any slipped through).
- `cb-analytics-mcp --version` and your Python version.

## Security issues

Don't open a public issue for security problems. See
[`SECURITY.md`](SECURITY.md).

## License

By contributing, you agree your contributions are licensed under the MIT
license, the same as the rest of the project.
