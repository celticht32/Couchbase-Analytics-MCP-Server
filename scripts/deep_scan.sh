#!/usr/bin/env bash
# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
#
# Deep scan: every static check + the full test suite.
# Exits non-zero on any failure. Used in CI and locally before commits.

set -euo pipefail

# Colours, if running in a terminal
if [[ -t 1 ]]; then
    GREEN="\033[32m"
    RED="\033[31m"
    BOLD="\033[1m"
    DIM="\033[2m"
    RESET="\033[0m"
else
    GREEN=""; RED=""; BOLD=""; DIM=""; RESET=""
fi

start_time=$(date +%s)
fails=()

run() {
    local label="$1"; shift
    local cmd="$*"
    printf "%b\n" "${BOLD}── ${label}${RESET} ${DIM}(${cmd})${RESET}"
    if eval "${cmd}"; then
        printf "%b\n" "${GREEN}✓ ${label}${RESET}\n"
    else
        printf "%b\n" "${RED}✗ ${label} FAILED${RESET}\n"
        fails+=("${label}")
    fi
}

# ── Static checks ─────────────────────────────────────────────────────────────

run "pyflakes (src)"        "pyflakes src"
run "ruff lint (src + tests)" "ruff check src tests"
run "ruff format check"     "ruff format --check src tests"
run "mypy strict (src)"     "mypy src"
run "bandit (src)"          "bandit -r src -c pyproject.toml -q"
run "pip-audit (project deps)" "pip-audit . --strict --progress-spinner=off"

# ── Smoke import ─────────────────────────────────────────────────────────────

run "smoke import" \
  "python -c \"from cb_analytics_mcp.server import build_server; from cb_analytics_mcp.gui.app import build_app; print('imports ok')\""

# ── Tests ────────────────────────────────────────────────────────────────────

run "pytest unit + coverage" "pytest tests/unit --cov --cov-report=term --cov-fail-under=80 -q"

# ── Summary ──────────────────────────────────────────────────────────────────

duration=$(( $(date +%s) - start_time ))
echo ""
printf "%b\n" "${BOLD}═══ Deep scan summary ═══${RESET}"
echo "Duration: ${duration}s"

if (( ${#fails[@]} == 0 )); then
    printf "%b\n" "${GREEN}${BOLD}All checks passed.${RESET}"
    exit 0
else
    printf "%b\n" "${RED}${BOLD}Failures:${RESET}"
    for f in "${fails[@]}"; do
        printf "  - %s\n" "$f"
    done
    exit 1
fi
