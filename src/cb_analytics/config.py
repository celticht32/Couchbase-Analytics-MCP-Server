# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Client configuration — reads from environment variables or explicit kwargs.

Environment variable names are prefixed with CB_ANALYTICS_:
  CB_ANALYTICS_HOST          → host
  CB_ANALYTICS_MGMT_PORT     → mgmt_port
  CB_ANALYTICS_ANALYTICS_PORT → analytics_port
  CB_ANALYTICS_USERNAME      → username
  CB_ANALYTICS_PASSWORD      → password
  CB_ANALYTICS_TLS           → tls
  CB_ANALYTICS_VERIFY_SSL    → verify_ssl
  CB_ANALYTICS_TIMEOUT       → timeout_seconds
  CB_ANALYTICS_MAX_RETRIES   → max_retries
"""

from __future__ import annotations

from pydantic import field_validator
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
    password: str = "password"
    tls: bool = False
    verify_ssl: bool = True
    timeout_seconds: float = 60.0
    max_retries: int = 3

    @field_validator("mgmt_port", "analytics_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be 1-65535, got {v}")
        return v

    @property
    def management_url(self) -> str:
        scheme = "https" if self.tls else "http"
        return f"{scheme}://{self.host}:{self.mgmt_port}"

    @property
    def analytics_url(self) -> str:
        scheme = "https" if self.tls else "http"
        return f"{scheme}://{self.host}:{self.analytics_port}"
