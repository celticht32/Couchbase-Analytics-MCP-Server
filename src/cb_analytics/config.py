# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Client configuration — reads from environment variables or explicit kwargs.

Environment variables are prefixed with CB_ANALYTICS_:
  CB_ANALYTICS_HOST               → host
  CB_ANALYTICS_MGMT_PORT          → mgmt_port
  CB_ANALYTICS_ANALYTICS_PORT     → analytics_port
  CB_ANALYTICS_USERNAME           → username
  CB_ANALYTICS_PASSWORD           → password  (stored as SecretStr)
  CB_ANALYTICS_TLS                → tls
  CB_ANALYTICS_VERIFY_SSL         → verify_ssl
  CB_ANALYTICS_TIMEOUT_SECONDS    → timeout_seconds
  CB_ANALYTICS_MAX_RETRIES        → max_retries
  CB_ANALYTICS_DEBUG              → debug  (logs request details, never passwords)
  CB_ANALYTICS_CIRCUIT_FAIL_MAX   → circuit_fail_max
  CB_ANALYTICS_CIRCUIT_RESET_TIMEOUT → circuit_reset_timeout
"""

from __future__ import annotations

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnalyticsClientConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CB_ANALYTICS_",
        env_file=".env",
        case_sensitive=False,
    )

    host: str = "localhost"
    mgmt_port: int = 8091
    analytics_port: int = 8095
    username: str = "Administrator"
    password: SecretStr = SecretStr("password")
    tls: bool = False
    verify_ssl: bool = True
    timeout_seconds: float = 60.0
    max_retries: int = 3

    # Debug mode: logs method+path. Never logs passwords.
    debug: bool = False

    # Circuit breaker: open after this many consecutive failures
    circuit_fail_max: int = 5
    # Seconds before circuit half-opens and allows a probe request
    circuit_reset_timeout: int = 30

    @field_validator("mgmt_port", "analytics_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be 1-65535, got {v}")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {v}")
        return v

    @property
    def management_url(self) -> str:
        scheme = "https" if self.tls else "http"
        port = 18091 if self.tls and self.mgmt_port == 8091 else self.mgmt_port
        return f"{scheme}://{self.host}:{port}"

    @property
    def analytics_url(self) -> str:
        scheme = "https" if self.tls else "http"
        port = 18095 if self.tls and self.analytics_port == 8095 else self.analytics_port
        return f"{scheme}://{self.host}:{port}"
