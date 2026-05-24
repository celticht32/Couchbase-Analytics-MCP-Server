# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Central configuration loaded from environment variables and optional JSON files.

All settings are loaded by `load_config()` which returns a single `AppConfig`
that the rest of the application reads from.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import SecretStr

# ── Per-cluster config ─────────────────────────────────────────────────────────


@dataclass
class ClusterConfig:
    name: str
    host: str
    username: str
    password: SecretStr
    mgmt_port: int = 8091
    analytics_port: int = 8095
    tls: bool = False
    verify_ssl: bool = True
    timeout_seconds: float = 60.0
    max_retries: int = 3


# ── GUI ────────────────────────────────────────────────────────────────────────


@dataclass
class GuiConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    username: str = "admin"
    password: SecretStr = field(default_factory=lambda: SecretStr("changeme"))
    session_secret: SecretStr = field(default_factory=lambda: SecretStr("CHANGE_ME"))


# ── Limits ─────────────────────────────────────────────────────────────────────


@dataclass
class LimitsConfig:
    """
    Tunable safety limits.

    All of these have sensible defaults; operators usually only override when
    a deployment has unusual traffic shape or a particularly large dataset.
    """

    # Maximum rows returned by execute_query / execute_query_readonly before
    # the response is truncated. Truncated responses include `truncated: true`
    # and `row_cap` so the caller (typically Claude) knows to use
    # execute_query_paginated for the full set. 0 disables the cap entirely.
    max_query_rows: int = 1000

    # Rate limits, per API key, per tool category, per second. These are
    # token-bucket rates — exceeding them produces a 429-equivalent
    # AnalyticsRequestError with retry_after. Set to 0 to disable.
    rate_limit_query_per_sec: int = 10  # execute_query, _readonly, _paginated, fetch_next_page, explain_query
    rate_limit_read_per_sec: int = 60  # everything else that's read-only
    rate_limit_write_per_sec: int = 1  # tools that mutate cluster state

    # Audit-log rotation. Rotation happens when the current file exceeds
    # `audit_rotate_bytes`; older files are renamed audit.log.1, .2, ...
    # up to `audit_rotate_keep`. Set audit_rotate_bytes to 0 to disable rotation.
    audit_rotate_bytes: int = 10 * 1024 * 1024  # 10 MB
    audit_rotate_keep: int = 5


# ── Observability ──────────────────────────────────────────────────────────────


@dataclass
class ObservabilityConfig:
    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "console"
    log_file: str | None = None

    audit_log_enabled: bool = True
    audit_log_file: str = "./audit.log"

    otel_enabled: bool = False
    otel_endpoint: str | None = None
    otel_service_name: str = "cb-analytics-mcp"

    metrics_enabled: bool = True
    metrics_port: int = 9100


# ── Full app config ────────────────────────────────────────────────────────────


@dataclass
class AppConfig:
    # MCP server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    mcp_api_key: SecretStr = field(default_factory=lambda: SecretStr(""))
    mcp_server_url: str = "http://localhost:8000"
    mcp_issuer_url: str = "http://localhost:8000"

    # Clusters
    clusters: list[ClusterConfig] = field(default_factory=list)

    # Capella
    capella_api_key: SecretStr | None = None
    capella_base_url: str = "https://cloudapi.cloud.couchbase.com"

    # GUI
    gui: GuiConfig = field(default_factory=GuiConfig)

    # Observability
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    # Limits (rate, row cap, audit rotation)
    limits: LimitsConfig = field(default_factory=LimitsConfig)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got '{val}'") from None


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except ValueError:
        raise ValueError(f"{name} must be a number, got '{val}'") from None


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_secret(name: str, default: str = "") -> SecretStr:
    return SecretStr(_env_str(name, default))


# ── Loaders ────────────────────────────────────────────────────────────────────


def load_clusters_from_file(path: str) -> list[ClusterConfig]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Cluster config file not found: {path}")

    raw = json.loads(p.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"Cluster file must contain a JSON array, got {type(raw).__name__}")

    result: list[ClusterConfig] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"Cluster entry {i} must be an object")
        if "host" not in entry:
            raise ValueError(f"Cluster entry {i} missing 'host'")
        if "password" not in entry:
            raise ValueError(f"Cluster entry {i} missing 'password'")

        result.append(
            ClusterConfig(
                name=entry.get("name", f"cluster-{i}"),
                host=entry["host"],
                username=entry.get("username", "Administrator"),
                password=SecretStr(entry["password"]),
                mgmt_port=int(entry.get("mgmt_port", 8091)),
                analytics_port=int(entry.get("analytics_port", 8095)),
                tls=bool(entry.get("tls", False)),
                verify_ssl=bool(entry.get("verify_ssl", True)),
                timeout_seconds=float(entry.get("timeout_seconds", 60.0)),
                max_retries=int(entry.get("max_retries", 3)),
            )
        )
    return result


def load_clusters_from_env() -> list[ClusterConfig]:
    host = _env_str("CB_ANALYTICS_HOST")
    password = _env_str("CB_ANALYTICS_PASSWORD")
    if not host or not password:
        return []

    return [
        ClusterConfig(
            name=_env_str("CB_ANALYTICS_CLUSTER_NAME", "default"),
            host=host,
            username=_env_str("CB_ANALYTICS_USERNAME", "Administrator"),
            password=SecretStr(password),
            mgmt_port=_env_int("CB_ANALYTICS_MGMT_PORT", 8091),
            analytics_port=_env_int("CB_ANALYTICS_ANALYTICS_PORT", 8095),
            tls=_env_bool("CB_ANALYTICS_TLS", False),
            verify_ssl=_env_bool("CB_ANALYTICS_VERIFY_SSL", True),
            timeout_seconds=_env_float("CB_ANALYTICS_TIMEOUT_SECONDS", 60.0),
            max_retries=_env_int("CB_ANALYTICS_MAX_RETRIES", 3),
        )
    ]


def load_gui_config() -> GuiConfig:
    return GuiConfig(
        enabled=_env_bool("GUI_ENABLED", True),
        host=_env_str("GUI_HOST", "0.0.0.0"),
        port=_env_int("GUI_PORT", 8080),
        username=_env_str("GUI_USERNAME", "admin"),
        password=_env_secret("GUI_PASSWORD", "changeme"),
        session_secret=_env_secret("GUI_SESSION_SECRET", "CHANGE_ME"),
    )


def load_observability_config() -> ObservabilityConfig:
    return ObservabilityConfig(
        log_level=_env_str("LOG_LEVEL", "INFO").upper(),
        log_format=_env_str("LOG_FORMAT", "json").lower(),
        log_file=_env_str("LOG_FILE") or None,
        audit_log_enabled=_env_bool("AUDIT_LOG_ENABLED", True),
        audit_log_file=_env_str("AUDIT_LOG_FILE", "./audit.log"),
        otel_enabled=_env_bool("OTEL_ENABLED", False),
        otel_endpoint=_env_str("OTEL_EXPORTER_OTLP_ENDPOINT") or None,
        otel_service_name=_env_str("OTEL_SERVICE_NAME", "cb-analytics-mcp"),
        metrics_enabled=_env_bool("METRICS_ENABLED", True),
        metrics_port=_env_int("METRICS_PORT", 9100),
    )


def load_config() -> AppConfig:
    """
    Load the full application configuration from environment variables
    (and optionally a multi-cluster JSON file).

    Returns a fully-populated AppConfig.
    Raises ValueError if required values are missing or malformed.
    """
    cfg = AppConfig(
        mcp_host=_env_str("MCP_HOST", "0.0.0.0"),
        mcp_port=_env_int("MCP_PORT", 8000),
        mcp_api_key=_env_secret("MCP_API_KEY"),
        mcp_server_url=_env_str("MCP_SERVER_URL", "http://localhost:8000"),
        mcp_issuer_url=_env_str("MCP_ISSUER_URL", "http://localhost:8000"),
        capella_base_url=_env_str("CB_CAPELLA_BASE_URL", "https://cloudapi.cloud.couchbase.com"),
        gui=load_gui_config(),
        observability=load_observability_config(),
        limits=load_limits_config(),
    )

    # Capella
    capella_key = _env_str("CB_CAPELLA_API_KEY_SECRET")
    if capella_key:
        cfg.capella_api_key = SecretStr(capella_key)

    # Clusters — file beats env vars
    cluster_file = _env_str("CB_ANALYTICS_CLUSTERS_FILE")
    if cluster_file:
        cfg.clusters = load_clusters_from_file(cluster_file)
    else:
        cfg.clusters = load_clusters_from_env()

    return cfg


def load_limits_config() -> LimitsConfig:
    """Read the LimitsConfig fields from environment variables."""
    return LimitsConfig(
        max_query_rows=_env_int("MAX_QUERY_ROWS", 1000),
        rate_limit_query_per_sec=_env_int("RATE_LIMIT_QUERY_PER_SEC", 10),
        rate_limit_read_per_sec=_env_int("RATE_LIMIT_READ_PER_SEC", 60),
        rate_limit_write_per_sec=_env_int("RATE_LIMIT_WRITE_PER_SEC", 1),
        audit_rotate_bytes=_env_int("AUDIT_ROTATE_BYTES", 10 * 1024 * 1024),
        audit_rotate_keep=_env_int("AUDIT_ROTATE_KEEP", 5),
    )


def validate_config(cfg: AppConfig, strict: bool = True) -> list[str]:
    """
    Validate the loaded config. Returns a list of human-readable errors.
    When `strict` is True, also requires MCP_API_KEY (server can't auth without it).
    """
    errors: list[str] = []

    if strict:
        if not cfg.mcp_api_key.get_secret_value():
            errors.append("MCP_API_KEY is required (min 32 characters)")
        elif len(cfg.mcp_api_key.get_secret_value()) < 32:
            errors.append("MCP_API_KEY must be at least 32 characters")

    if not cfg.clusters:
        errors.append(
            "No clusters configured. Set CB_ANALYTICS_HOST + CB_ANALYTICS_PASSWORD "
            "or CB_ANALYTICS_CLUSTERS_FILE."
        )

    seen: set[str] = set()
    for c in cfg.clusters:
        if c.name in seen:
            errors.append(f"Duplicate cluster name: {c.name}")
        seen.add(c.name)

    if cfg.gui.enabled:
        if cfg.gui.session_secret.get_secret_value() in ("", "CHANGE_ME"):
            errors.append(
                "GUI_SESSION_SECRET must be set when GUI is enabled "
                "(use `python -c 'import secrets; print(secrets.token_urlsafe(48))'`)"
            )
        if cfg.gui.password.get_secret_value() == "changeme" and strict:
            errors.append("GUI_PASSWORD is at default 'changeme' — change it")

    if cfg.observability.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        errors.append(f"Invalid LOG_LEVEL: {cfg.observability.log_level}")

    return errors


def config_summary(cfg: AppConfig) -> dict[str, Any]:
    """Produce a redacted summary of the config for logging."""
    return {
        "mcp": {
            "host": cfg.mcp_host,
            "port": cfg.mcp_port,
            "api_key_set": bool(cfg.mcp_api_key.get_secret_value()),
            "server_url": cfg.mcp_server_url,
        },
        "clusters": [
            {
                "name": c.name,
                "host": c.host,
                "username": c.username,
                "tls": c.tls,
            }
            for c in cfg.clusters
        ],
        "capella": {"configured": cfg.capella_api_key is not None},
        "gui": {
            "enabled": cfg.gui.enabled,
            "host": cfg.gui.host,
            "port": cfg.gui.port,
            "username": cfg.gui.username,
        },
        "observability": {
            "log_level": cfg.observability.log_level,
            "log_format": cfg.observability.log_format,
            "log_file": cfg.observability.log_file,
            "audit_log_enabled": cfg.observability.audit_log_enabled,
            "audit_log_file": cfg.observability.audit_log_file,
            "otel_enabled": cfg.observability.otel_enabled,
            "metrics_enabled": cfg.observability.metrics_enabled,
        },
    }
