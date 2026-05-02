# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Low-level async HTTP client wrapping httpx.
Handles:
  - Basic authentication
  - Configurable timeouts
  - Automatic retry with exponential backoff (tenacity)
  - Structured error response parsing
  - Both HTTP/8091 (management) and HTTP/8095 (analytics) base URLs
"""

from __future__ import annotations

import asyncio
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
    AnalyticsConnectionError,
    AnalyticsNotFoundError,
    AnalyticsRequestError,
    AnalyticsServerError,
)

log = structlog.get_logger(__name__)


class HttpClient:
    """
    Async HTTP client with retry logic and structured error handling.

    Args:
        management_url: Base URL for the management API (port 8091 by default).
        analytics_url: Base URL for the Analytics API (port 8095 by default).
        username: Couchbase RBAC username.
        password: Couchbase RBAC password.
        timeout: Request timeout in seconds.
        verify_ssl: Whether to verify TLS certificates.
        max_retries: Maximum number of retry attempts for transient errors.
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
        self._auth = (username, password)
        self._timeout = httpx.Timeout(timeout)
        self._max_retries = max_retries
        self._verify_ssl = verify_ssl

        self._mgmt_client = httpx.AsyncClient(
            base_url=management_url,
            auth=self._auth,
            timeout=self._timeout,
            verify=verify_ssl,
            headers={"Accept": "application/json"},
        )
        self._analytics_client = httpx.AsyncClient(
            base_url=analytics_url,
            auth=self._auth,
            timeout=self._timeout,
            verify=verify_ssl,
            headers={"Accept": "application/json"},
        )

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._mgmt_client.aclose()
        await self._analytics_client.aclose()

    # ── Public request methods ────────────────────────────────────────────────

    async def mgmt_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET against the management API (port 8091)."""
        return await self._request(self._mgmt_client, "GET", path, params=params)

    async def mgmt_post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            self._mgmt_client, "POST", path, data=data, json=json, params=params
        )

    async def mgmt_put(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            self._mgmt_client, "PUT", path, data=data, json=json, params=params
        )

    async def mgmt_patch(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        return await self._request(self._mgmt_client, "PATCH", path, data=data, json=json)

    async def mgmt_delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(self._mgmt_client, "DELETE", path, params=params)

    async def analytics_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET against the Analytics API (port 8095)."""
        return await self._request(self._analytics_client, "GET", path, params=params)

    async def analytics_post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            self._analytics_client, "POST", path, data=data, json=json, params=params
        )

    async def analytics_put(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        return await self._request(self._analytics_client, "PUT", path, data=data, json=json)

    async def analytics_delete(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._request(self._analytics_client, "DELETE", path, params=params)

    # ── Internal implementation ───────────────────────────────────────────────

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
        """Execute an HTTP request with retry logic."""
        log.debug("http_request", method=method, path=path)

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((AnalyticsConnectionError, AnalyticsServerError)),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await client.request(
                        method,
                        path,
                        data=data,
                        json=json,
                        params={k: v for k, v in (params or {}).items() if v is not None},
                    )
                    return self._handle_response(response)
                except httpx.ConnectError as e:
                    raise AnalyticsConnectionError(str(e)) from e
                except httpx.TimeoutException as e:
                    raise AnalyticsConnectionError(f"Timeout: {e}") from e

        return None  # unreachable but satisfies mypy

    def _handle_response(self, response: httpx.Response) -> Any:
        """Parse response or raise a domain exception."""
        status = response.status_code

        if status == 204:
            return None

        # Try to parse JSON body for all responses
        body: Any = None
        try:
            body = response.json()
        except Exception:
            body = response.text

        if status == 200 or status == 201 or status == 202:
            return body

        if status == 401:
            raise AnalyticsAuthError(f"Authentication failed: {body}")
        if status == 403:
            raise AnalyticsAuthError(f"Authorization failed: {body}")
        if status == 404:
            raise AnalyticsNotFoundError(f"Resource not found: {body}")
        if status == 400:
            raise AnalyticsRequestError(f"Bad request: {body}")
        if status == 409:
            raise AnalyticsRequestError(f"Conflict: {body}")
        if status >= 500:
            raise AnalyticsServerError(f"Server error {status}: {body}")

        raise AnalyticsRequestError(f"Unexpected status {status}: {body}")
