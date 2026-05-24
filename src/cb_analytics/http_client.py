# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Low-level async HTTP client.

Features:
  - Basic authentication (password plain str; SecretStr unwrapped by AnalyticsClient)
  - asyncio.timeout outer guard on every request
  - Manual async circuit breaker (replaces pybreaker which requires Tornado on Python 3.12)
  - Automatic retry with exponential backoff (tenacity)
  - Prometheus metrics via MetricsRegistry
  - Structured logging (never logs passwords)
  - SQL++ injection warning for interpolated statements
"""

from __future__ import annotations

import asyncio
import re
import time
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cb_analytics.exceptions import (
    AnalyticsAuthError,
    AnalyticsCircuitOpenError,
    AnalyticsConnectionError,
    AnalyticsNotFoundError,
    AnalyticsRequestError,
    AnalyticsServerError,
)

try:
    from cb_analytics.observability.metrics import MetricsRegistry
except ImportError:
    MetricsRegistry = None  # type: ignore[assignment,misc]

log = structlog.get_logger(__name__)

# Matches f-strings, %-format, .format(), or bare {…} in plain strings
_INTERPOLATION_RE = re.compile(
    r'(f["\'].*?\{.*?\}|%[sd]|\.format\(|\{[^}]+\})',
    re.DOTALL,
)


def _warn_if_interpolated(statement: str) -> None:
    """Emit a UserWarning if the statement looks like it was built with string interpolation."""
    if _INTERPOLATION_RE.search(statement):
        warnings.warn(
            "SQL++ statement may contain string-interpolated values. "
            "Use parameterized queries (args= or named_args=) to prevent injection risks.",
            UserWarning,
            stacklevel=4,
        )


# ── Manual Async Circuit Breaker ──────────────────────────────────────────────

class _CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _AsyncCircuitBreaker:
    """
    Minimal async-native circuit breaker — no Tornado dependency.

    States:
      CLOSED     → requests pass through; failures counted
      OPEN       → requests rejected immediately after fail_max failures
      HALF_OPEN  → one probe request allowed after reset_timeout seconds
    """

    fail_max: int = 5
    reset_timeout: float = 30.0
    _state: _CBState = field(default=_CBState.CLOSED, init=False)
    _fail_count: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> _CBState:
        return self._state

    async def call(self, coro_func: Any, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            if self._state == _CBState.OPEN:
                if time.monotonic() - self._opened_at >= self.reset_timeout:
                    self._state = _CBState.HALF_OPEN
                else:
                    raise AnalyticsCircuitOpenError(
                        f"Circuit breaker OPEN — retry after "
                        f"{self.reset_timeout - (time.monotonic() - self._opened_at):.0f}s"
                    )

        try:
            result = await coro_func(*args, **kwargs)
            async with self._lock:
                # Success: reset counter
                self._fail_count = 0
                if self._state == _CBState.HALF_OPEN:
                    self._state = _CBState.CLOSED
            return result
        except AnalyticsCircuitOpenError:
            raise
        except Exception:
            async with self._lock:
                self._fail_count += 1
                if self._fail_count >= self.fail_max or self._state == _CBState.HALF_OPEN:
                    self._state = _CBState.OPEN
                    self._opened_at = time.monotonic()
            raise


# ── HTTP Client ───────────────────────────────────────────────────────────────

class HttpClient:
    """
    Async HTTP client with circuit breaker, retry, and optional metrics.

    Args:
        management_url:        Base URL for the management API (port 8091).
        analytics_url:         Base URL for the Analytics API (port 8095).
        username:              Couchbase RBAC username.
        password:              Plain string password (SecretStr unwrapped by caller).
        timeout:               Per-request timeout in seconds.
        verify_ssl:            Whether to verify TLS certificates.
        max_retries:           Maximum retry attempts for transient errors.
        debug:                 Log request method+path (never logs password).
        circuit_fail_max:      Consecutive failures before circuit opens.
        circuit_reset_timeout: Seconds before circuit allows a probe.
        metrics:               Optional MetricsRegistry for Prometheus tracking.
    """

    def __init__(
        self,
        management_url: str,
        analytics_url: str,
        username: str,
        password: str,
        timeout: float = 60.0,
        verify_ssl: bool = True,
        max_retries: int = 3,
        debug: bool = False,
        circuit_fail_max: int = 5,
        circuit_reset_timeout: int = 30,
        metrics: Any = None,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._debug = debug
        self._metrics = metrics

        auth = (username, password)

        self._mgmt_client = httpx.AsyncClient(
            base_url=management_url,
            auth=auth,
            timeout=httpx.Timeout(timeout),
            verify=verify_ssl,
            headers={"Accept": "application/json"},
        )
        self._analytics_client = httpx.AsyncClient(
            base_url=analytics_url,
            auth=auth,
            timeout=httpx.Timeout(timeout),
            verify=verify_ssl,
            headers={"Accept": "application/json"},
        )
        self._breaker = _AsyncCircuitBreaker(
            fail_max=circuit_fail_max,
            reset_timeout=float(circuit_reset_timeout),
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._mgmt_client.aclose()
        await self._analytics_client.aclose()

    # ── Management API ─────────────────────────────────────────────────────────

    async def mgmt_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(self._mgmt_client, "GET", path, params=params)

    async def mgmt_post(
        self, path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(self._mgmt_client, "POST", path, data=data, json=json, params=params)

    async def mgmt_put(
        self, path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(self._mgmt_client, "PUT", path, data=data, json=json, params=params)

    async def mgmt_patch(self, path: str, data: dict[str, Any] | None = None, json: Any = None) -> Any:
        return await self._request(self._mgmt_client, "PATCH", path, data=data, json=json)

    async def mgmt_delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(self._mgmt_client, "DELETE", path, params=params)

    # ── Analytics API ──────────────────────────────────────────────────────────

    async def analytics_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(self._analytics_client, "GET", path, params=params)

    async def analytics_post(
        self, path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(self._analytics_client, "POST", path, data=data, json=json, params=params)

    async def analytics_put(self, path: str, data: dict[str, Any] | None = None, json: Any = None) -> Any:
        return await self._request(self._analytics_client, "PUT", path, data=data, json=json)

    async def analytics_delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(self._analytics_client, "DELETE", path, params=params)

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if self._debug:
            log.debug("http_request", method=method, path=path)

        clean_params = {k: v for k, v in (params or {}).items() if v is not None} or None

        async def _do_request() -> Any:
            async with asyncio.timeout(self._timeout + 5):
                return await client.request(
                    method, path,
                    data=data,
                    json=json,
                    params=clean_params,
                )

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((AnalyticsConnectionError, AnalyticsServerError)),
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
                reraise=True,
            ):
                with attempt:
                    try:
                        if self._metrics:
                            with self._metrics.track_request(method, path):
                                response = await self._breaker.call(_do_request)
                        else:
                            response = await self._breaker.call(_do_request)
                        return self._handle_response(response)
                    except AnalyticsCircuitOpenError:
                        raise  # Don't retry circuit-open errors — let tenacity see it as non-retryable
                    except httpx.ConnectError as e:
                        raise AnalyticsConnectionError(str(e)) from e
                    except httpx.TimeoutException as e:
                        raise AnalyticsConnectionError(f"Timeout: {e}") from e
                    except TimeoutError as e:
                        raise AnalyticsConnectionError(f"asyncio timeout: {e}") from e
        except AnalyticsCircuitOpenError:
            raise
        return None  # unreachable; satisfies mypy

    def _handle_response(self, response: httpx.Response) -> Any:
        status = response.status_code

        if status == 204:
            return None

        body: Any = None
        try:
            body = response.json()
        except Exception:
            body = response.text or None

        if status in (200, 201, 202):
            return body

        if status == 401:
            raise AnalyticsAuthError("Authentication failed (401)")
        if status == 403:
            raise AnalyticsAuthError("Authorization failed (403)")
        if status == 404:
            raise AnalyticsNotFoundError(f"Resource not found (404): {_safe(body)}")
        if status == 400:
            raise AnalyticsRequestError(f"Bad request (400): {_safe(body)}")
        if status == 409:
            raise AnalyticsRequestError(f"Conflict (409): {_safe(body)}")
        if status >= 500:
            raise AnalyticsServerError(f"Server error ({status}): {_safe(body)}")

        raise AnalyticsRequestError(f"Unexpected status {status}: {_safe(body)}")


def _safe(body: Any) -> str:
    return str(body)[:400] if body is not None else ""
