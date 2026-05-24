<!--
Thanks for the contribution! A few quick checks before you submit.
-->

## What this changes

A short summary of the user-visible behaviour change, or "internal refactor"
if there isn't one.

## Why

Link an issue if there is one. Otherwise describe the problem this solves.

## How to test

The reviewer will run `make scan`. If your change needs special setup
(real Couchbase, a Capella sandbox, env vars), say so here.

## Checklist

- [ ] `make scan` passes locally (pyflakes + ruff + mypy strict + bandit + pytest)
- [ ] Coverage is still ≥ 80 %
- [ ] Added tests for new behaviour
- [ ] Updated `CHANGELOG.md` under `## [Unreleased]`
- [ ] Updated docs (`docs/` or skill files) if behaviour changed
- [ ] No new secrets in logs (redactor still catches them)
