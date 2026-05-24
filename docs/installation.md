# Installation

## Requirements

- Python 3.11, 3.12, or 3.13
- Network access from the server to your Couchbase management port
  (`8091` / `18091`) and Analytics port (`8095` / `18095`)
- For Capella tools: a Capella Management API key

## Install from source

```bash
git clone https://github.com/celticht32/cb-analytics-mcp
cd cb-analytics-mcp
make dev
```

`make dev` creates a virtualenv at `.venv/` and installs runtime + dev
dependencies.

If you prefer a one-shot install without the venv wrapper:

```bash
pip install -e ".[dev]"
```

## First run

```bash
cp .env.example .env
# Edit .env to set MCP_API_KEY, CB_ANALYTICS_HOST, CB_ANALYTICS_PASSWORD,
# GUI_PASSWORD, GUI_SESSION_SECRET.
make run
```

You should see two ports listening:

```
[info] server_starting       host=0.0.0.0 mcp_port=8000
[info] gui_app_built         host=0.0.0.0 gui_port=8080
```

Visit `http://localhost:8080` to see the GUI; sign in with `GUI_USERNAME` /
`GUI_PASSWORD`.

## Validate without running

`--check` validates the configuration and exits:

```bash
cb-analytics-mcp --check
```

A clean run prints `config_valid` and exits 0.

## Generating screenshots

The docs include screenshots regenerated locally by:

```bash
make screenshots
```

This launches an in-process FastAPI server, drives a headless Chromium
through every page, and writes PNGs into `docs/img/`.

## Docker

A `Dockerfile` and `docker-compose.yml` are provided for production use.
See [Deployment](deployment.md).
