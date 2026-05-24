# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Tests for HttpClient, circuit breaker, retry, error mapping, and models."""

from __future__ import annotations

import pytest
import respx
import httpx

from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.exceptions import (
    AnalyticsAuthError,
    AnalyticsNotFoundError,
    AnalyticsRequestError,
    AnalyticsServerError,
)
from cb_analytics.http_client import HttpClient, _warn_if_interpolated
from cb_analytics.models import (
    AzureBlobLinkConfig,
    GCSLinkConfig,
    IngestionStatus,
    S3LinkConfig,
    ServiceConfig,
)
from tests.conftest import ANALYTICS_BASE, MGMT_BASE, make_response


# ── HTTP status → exception mapping ──────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_200_returns_body(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(return_value=make_response({"uuid": "abc"}))
    result = await http.mgmt_get("/pools")
    assert result["uuid"] == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_204_returns_none(http: HttpClient) -> None:
    respx.post(f"{MGMT_BASE}/controller/cancelLogsCollection").mock(return_value=httpx.Response(204))
    result = await http.mgmt_post("/controller/cancelLogsCollection")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_401_raises_auth_error(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/users").mock(
        return_value=httpx.Response(401, json={"message": "Unauthorized"})
    )
    with pytest.raises(AnalyticsAuthError):
        await http.mgmt_get("/settings/rbac/users")


@respx.mock
@pytest.mark.asyncio
async def test_403_raises_auth_error(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/settings/security").mock(return_value=httpx.Response(403))
    with pytest.raises(AnalyticsAuthError):
        await http.mgmt_get("/settings/security")


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_not_found(http: HttpClient) -> None:
    respx.get(f"{ANALYTICS_BASE}/api/v1/link/nope").mock(return_value=httpx.Response(404))
    with pytest.raises(AnalyticsNotFoundError):
        await http.analytics_get("/api/v1/link/nope")


@respx.mock
@pytest.mark.asyncio
async def test_400_raises_request_error(http: HttpClient) -> None:
    respx.post(f"{MGMT_BASE}/clusterInit").mock(return_value=httpx.Response(400, json=["bad param"]))
    with pytest.raises(AnalyticsRequestError):
        await http.mgmt_post("/clusterInit", data={"services": "invalid"})


@respx.mock
@pytest.mark.asyncio
async def test_409_raises_request_error(http: HttpClient) -> None:
    respx.put(f"{MGMT_BASE}/settings/rbac/users/local/alice").mock(return_value=httpx.Response(409))
    with pytest.raises(AnalyticsRequestError):
        await http.mgmt_put("/settings/rbac/users/local/alice", data={"password": "x"})


@respx.mock
@pytest.mark.asyncio
async def test_500_raises_server_error(http: HttpClient) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(return_value=httpx.Response(500))
    with pytest.raises(AnalyticsServerError):
        await http.mgmt_get("/pools")


# ── None params filtering ─────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_none_params_not_sent(http: HttpClient) -> None:
    route = respx.get(f"{MGMT_BASE}/events").mock(return_value=make_response([]))
    await http.mgmt_get("/events", params={"since": None, "limit": 10})
    url = str(route.calls[0].request.url)
    assert "since" not in url
    assert "limit=10" in url


# ── Secret not logged ─────────────────────────────────────────────────────────

def test_http_client_does_not_store_plaintext_password() -> None:
    """Confirm HttpClient doesn't expose password in repr or attributes."""
    client = HttpClient(
        management_url="http://localhost:8091",
        analytics_url="http://localhost:8095",
        username="admin",
        password="supersecret",
    )
    # repr should not contain the password
    assert "supersecret" not in repr(client)
    # _auth tuple is stored but not publicly accessible via named attribute
    assert not hasattr(client, "password")


# ── SQL injection warning ─────────────────────────────────────────────────────

def test_warn_if_interpolated_triggers() -> None:
    """Statements that look interpolated should emit a warning."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _warn_if_interpolated("SELECT * FROM ds WHERE id = {user_input}")
    assert len(w) == 1
    assert "parameterized" in str(w[0].message).lower()


def test_warn_if_interpolated_clean() -> None:
    """Clean parameterized statements should not warn."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _warn_if_interpolated("SELECT * FROM ds WHERE id = $1")
    assert len(w) == 0


# ── AnalyticsClient ping ──────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_client_ping_success(config: AnalyticsClientConfig) -> None:
    from cb_analytics.client import AnalyticsClient
    respx.get(f"{MGMT_BASE}/pools").mock(return_value=make_response({"pools": [], "uuid": "abc"}))
    async with AnalyticsClient(config) as client:
        assert await client.ping() is True


@respx.mock
@pytest.mark.asyncio
async def test_client_ping_failure(config: AnalyticsClientConfig) -> None:
    from cb_analytics.client import AnalyticsClient
    respx.get(f"{MGMT_BASE}/pools").mock(return_value=httpx.Response(500))
    async with AnalyticsClient(config) as client:
        assert await client.ping() is False


# ── SecretStr in config ───────────────────────────────────────────────────────

def test_config_password_is_secret_str() -> None:
    from pydantic import SecretStr
    config = AnalyticsClientConfig(password="my-password")  # type: ignore[arg-type]
    assert isinstance(config.password, SecretStr)
    # Must not appear in repr
    assert "my-password" not in repr(config)
    assert "my-password" not in str(config)
    # But accessible via get_secret_value()
    assert config.password.get_secret_value() == "my-password"


def test_config_tls_auto_port() -> None:
    """TLS=True with default ports should auto-select 18091/18095."""
    config = AnalyticsClientConfig(tls=True, host="cluster")
    assert config.management_url == "https://cluster:18091"
    assert config.analytics_url == "https://cluster:18095"


def test_config_tls_custom_port_preserved() -> None:
    config = AnalyticsClientConfig(tls=True, mgmt_port=9091, analytics_port=9095, host="cluster")
    assert ":9091" in config.management_url
    assert ":9095" in config.analytics_url


# ── Model: IngestionStatus.from_raw ──────────────────────────────────────────

def test_ingestion_status_from_list() -> None:
    raw = [{"name": "Local", "state": "CONNECTED", "datasetStates": []}]
    result = IngestionStatus.from_raw(raw)
    assert len(result.links) == 1
    assert result.links[0].name == "Local"


def test_ingestion_status_from_dict() -> None:
    raw = {"links": [{"name": "S3", "state": "CONNECTED"}]}
    result = IngestionStatus.from_raw(raw)
    assert result.links[0].name == "S3"


def test_ingestion_status_empty() -> None:
    result = IngestionStatus.from_raw(None)
    assert result.links == []


# ── Model: ServiceConfig.to_api_dict ─────────────────────────────────────────

def test_service_config_to_api_dict_excludes_unset() -> None:
    """Only explicitly set fields are included — 0 and False are preserved."""
    cfg = ServiceConfig(resultTtl=0)
    d = cfg.to_api_dict()
    assert "resultTtl" in d
    assert d["resultTtl"] == 0
    assert "storageBuffercacheSize" not in d


def test_service_config_to_api_dict_false_preserved() -> None:
    """ServiceConfig fields set to 0 are NOT None and must be sent."""
    cfg = ServiceConfig(compilerParallelism=0)
    d = cfg.to_api_dict()
    assert d.get("compilerParallelism") == 0


# ── Model: credentials ────────────────────────────────────────────────────────

def test_s3_link_secret_access_key_is_secret_str() -> None:
    from pydantic import SecretStr
    link = S3LinkConfig(region="us-east-1", accessKeyId="AKID", secretAccessKey="SECRET")
    assert isinstance(link.secretAccessKey, SecretStr)
    assert "SECRET" not in repr(link)
    d = link.to_api_dict()
    assert d["secretAccessKey"] == "SECRET"  # unwrapped at serialization


def test_azure_link_requires_key_or_sas() -> None:
    with pytest.raises(Exception):
        AzureBlobLinkConfig(accountName="myaccount")


def test_azure_link_with_sas() -> None:
    link = AzureBlobLinkConfig(accountName="myaccount", sharedAccessSignature="sv=2021&sig=xxx")
    d = link.to_api_dict()
    assert d["sharedAccessSignature"] == "sv=2021&sig=xxx"


def test_gcs_link_credentials_not_in_repr() -> None:
    link = GCSLinkConfig(jsonCredentials='{"type":"service_account","private_key":"secret"}')
    assert "secret" not in repr(link)
    d = link.to_api_dict()
    assert "secret" in d["jsonCredentials"]


# ── Exception hierarchy ───────────────────────────────────────────────────────

def test_exception_hierarchy() -> None:
    from cb_analytics.exceptions import (
        AnalyticsError, AnalyticsAuthError, AnalyticsConnectionError,
        AnalyticsNotFoundError, AnalyticsRequestError, AnalyticsServerError,
        AnalyticsQueryError, AnalyticsCircuitOpenError, AnalyticsLibraryError,
        AnalyticsConfigError,
    )
    for exc_type in [
        AnalyticsAuthError, AnalyticsConnectionError, AnalyticsNotFoundError,
        AnalyticsRequestError, AnalyticsServerError, AnalyticsQueryError,
        AnalyticsCircuitOpenError, AnalyticsLibraryError, AnalyticsConfigError,
    ]:
        assert issubclass(exc_type, AnalyticsError)


def test_query_error_str_with_location() -> None:
    from cb_analytics.exceptions import AnalyticsQueryError
    err = AnalyticsQueryError("Syntax error", code=24000, line=1, column=8)
    s = str(err)
    assert "Syntax error" in s
    assert "24000" in s
    assert "line 1" in s
    assert "column 8" in s


def test_query_error_str_without_location() -> None:
    from cb_analytics.exceptions import AnalyticsQueryError
    err = AnalyticsQueryError("Runtime error", code=25000)
    s = str(err)
    assert "25000" in s
    assert "line" not in s
