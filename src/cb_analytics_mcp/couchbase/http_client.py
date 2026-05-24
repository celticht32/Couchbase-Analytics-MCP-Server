# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Async HTTP client wrapping httpx with retry, circuit-breaker, and consistent
exception mapping for Couchbase REST endpoints.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsAuthError,
    AnalyticsCircuitOpenError,
    AnalyticsConnectionError,
    AnalyticsNotFoundError,
    AnalyticsRequestError,
    AnalyticsServerError,
)

log = structlog.get_logger(__name__)


class _AsyncCircuitBreaker:
    """
    Minimal asyncio-native circuit breaker.

    States: CLOSED → OPEN (after fail_max consecutive failures) →
    HALF_OPEN (after reset_timeout seconds) → CLOSED on first success
    or OPEN again on failure.

    Excluded exceptions don't count toward the failure count.
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        fail_max: int = 5,
        reset_timeout: float = 30.0,
        excluded_exceptions: tuple[type[BaseException], ...] = (),
    ) -> None:
        self._fail_max = fail_max
        self._reset_timeout = reset_timeout
        self._excluded = excluded_exceptions
        self._state = self.STATE_CLOSED
        self._fail_count = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def _maybe_half_open(self) -> None:
        if self._state == self.STATE_OPEN:
            if time.monotonic() - self._opened_at >= self._reset_timeout:
                self._state = self.STATE_HALF_OPEN

    async def _on_success(self) -> None:
        async with self._lock:
            self._fail_count = 0
            self._state = self.STATE_CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._fail_count += 1
            if self._fail_count >= self._fail_max:
                self._state = self.STATE_OPEN
                self._opened_at = time.monotonic()

    async def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            await self._maybe_half_open()
            if self._state == self.STATE_OPEN:
                raise AnalyticsCircuitOpenError(f"Circuit breaker open (failures={self._fail_count})")

        try:
            result = await func(*args, **kwargs)
        except self._excluded:
            # Allowed exceptions don't count toward failures
            raise
        except Exception:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result


class HttpClient:
    """
    Async HTTP wrapper around httpx.AsyncClient with:

    - Basic-auth (username + password)
    - Exponential-backoff retries on connection errors and 5xx
    - Circuit breaker (auto-open after repeated failures)
    - Consistent exception mapping (4xx/5xx → typed exceptions)
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
    ) -> None:
        self.management_url = management_url.rstrip("/")
        self.analytics_url = analytics_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout
        self._max_retries = max_retries

        self._client = httpx.AsyncClient(
            auth=(username, password),
            timeout=timeout,
            verify=verify_ssl,
            follow_redirects=True,
        )

        # Circuit breaker — open after 5 consecutive failures, half-open after 30s.
        # Auth/not-found/4xx are caller errors and don't trip the breaker.
        self._breaker = _AsyncCircuitBreaker(
            fail_max=5,
            reset_timeout=30.0,
            excluded_exceptions=(
                AnalyticsAuthError,
                AnalyticsNotFoundError,
                AnalyticsRequestError,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ── Public verb methods ────────────────────────────────────────────────────

    async def get_mgmt(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", self.management_url + path, **kwargs)

    async def post_mgmt(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("POST", self.management_url + path, **kwargs)

    async def put_mgmt(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("PUT", self.management_url + path, **kwargs)

    async def delete_mgmt(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("DELETE", self.management_url + path, **kwargs)

    async def get_analytics(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", self.analytics_url + path, **kwargs)

    async def post_analytics(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("POST", self.analytics_url + path, **kwargs)

    async def put_analytics(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("PUT", self.analytics_url + path, **kwargs)

    async def delete_analytics(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self._request("DELETE", self.analytics_url + path, **kwargs)

    # ── Core request loop ──────────────────────────────────────────────────────

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        result = await self._breaker.call(self._do_request, method, url, **kwargs)
        # _do_request is typed httpx.Response; breaker.call returns Any
        return result  # type: ignore[no-any-return]

    async def _do_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
            retry=retry_if_exception_type(
                (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError, AnalyticsServerError)
            ),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await self._client.request(method, url, **kwargs)
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                    log.warning("http_connect_error", method=method, url=url, error=str(e))
                    raise AnalyticsConnectionError(str(e)) from e
                except httpx.HTTPError as e:
                    raise AnalyticsConnectionError(str(e)) from e

                self._map_response_to_exception(response, method, url)
                return response

        # Unreachable; AsyncRetrying always re-raises or yields once.
        raise AnalyticsConnectionError("retry loop exhausted")  # pragma: no cover

    @staticmethod
    def _map_response_to_exception(response: httpx.Response, method: str, url: str) -> None:
        """Raise the right typed exception based on HTTP status code."""
        if 200 <= response.status_code < 300:
            return

        body = response.text[:500]  # truncate to avoid log spam
        status = response.status_code

        log.warning(
            "http_error_response",
            method=method,
            url=url,
            status_code=status,
            body_excerpt=body,
        )

        if status in (401, 403):
            raise AnalyticsAuthError(f"HTTP {status}: {body}")
        if status == 404:
            raise AnalyticsNotFoundError(f"HTTP {status}: {body}")
        if 400 <= status < 500:
            raise AnalyticsRequestError(f"HTTP {status}: {body}", status_code=status)
        # 5xx — retryable
        raise AnalyticsServerError(f"HTTP {status}: {body}", status_code=status)
