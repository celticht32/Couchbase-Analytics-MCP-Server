# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Unit tests for ServerGroupsAPI, model validation, and exceptions."""

from __future__ import annotations

import pytest
import respx

from cb_analytics.api.server_groups import ServerGroupsAPI
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.exceptions import (
    AnalyticsAuthError,
    AnalyticsConnectionError,
    AnalyticsNotFoundError,
    AnalyticsQueryError,
    AnalyticsRequestError,
    AnalyticsServerError,
)
from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    AnalyticsError,
    AnalyticsMetrics,
    AnalyticsQueryResponse,
    AzureBlobLinkConfig,
    ClusterInitRequest,
    GCSLinkConfig,
    LinkType,
    S3LinkConfig,
    ServerGroupCreateRequest,
    ServerGroupMembershipUpdate,
    ServerGroupUpdateRequest,
)
from tests.conftest import MGMT_BASE, make_response, empty_response


@pytest.fixture
def sg_api(config: AnalyticsClientConfig) -> ServerGroupsAPI:
    http = HttpClient(
        management_url=MGMT_BASE,
        analytics_url="http://localhost:8095",
        username=config.username,
        password=config.password,
        timeout=10.0,
        verify_ssl=False,
        max_retries=1,
    )
    return ServerGroupsAPI(http)


# ── Server Groups ─────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_groups(sg_api: ServerGroupsAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/serverGroups").mock(
        return_value=make_response({
            "groups": [
                {"name": "Group 1", "uri": "/pools/default/serverGroups/g1", "nodes": []},
                {"name": "Group 2", "uri": "/pools/default/serverGroups/g2", "nodes": []},
            ],
            "uri": "/pools/default/serverGroups",
            "rev": 5,
        })
    )
    result = await sg_api.get_groups()
    assert len(result.groups) == 2
    assert result.rev == 5
    assert result.groups[0].name == "Group 1"


@respx.mock
@pytest.mark.asyncio
async def test_create_group(sg_api: ServerGroupsAPI) -> None:
    respx.post(f"{MGMT_BASE}/pools/default/serverGroups").mock(
        return_value=make_response({"name": "Rack A", "uri": "/pools/default/serverGroups/abc"})
    )
    group = await sg_api.create_group(ServerGroupCreateRequest(name="Rack A"))
    assert group.name == "Rack A"


@respx.mock
@pytest.mark.asyncio
async def test_add_node_to_group(sg_api: ServerGroupsAPI) -> None:
    respx.post(f"{MGMT_BASE}/pools/default/serverGroups/uuid1/addNode").mock(
        return_value=empty_response(200)
    )
    await sg_api.add_node_to_group("uuid1", "ns_1@node2")


@respx.mock
@pytest.mark.asyncio
async def test_rename_group(sg_api: ServerGroupsAPI) -> None:
    respx.put(f"{MGMT_BASE}/pools/default/serverGroups/uuid1").mock(
        return_value=empty_response(200)
    )
    await sg_api.rename_group("uuid1", ServerGroupUpdateRequest(name="Rack B"))


@respx.mock
@pytest.mark.asyncio
async def test_update_group_membership(sg_api: ServerGroupsAPI) -> None:
    respx.put(f"{MGMT_BASE}/pools/default/serverGroups").mock(
        return_value=empty_response(200)
    )
    await sg_api.update_group_membership(
        rev=7,
        update=ServerGroupMembershipUpdate(
            groups=[{"name": "Group 1", "nodes": [{"otpNode": "ns_1@node1"}]}]
        ),
    )


@respx.mock
@pytest.mark.asyncio
async def test_delete_group(sg_api: ServerGroupsAPI) -> None:
    respx.delete(f"{MGMT_BASE}/pools/default/serverGroups/uuid1").mock(
        return_value=empty_response(200)
    )
    await sg_api.delete_group("uuid1")


# ── Model Validation ──────────────────────────────────────────────────────────


class TestClusterInitRequestModel:
    def test_required_fields(self) -> None:
        req = ClusterInitRequest(username="admin", password="pass", services="kv,cbas")
        assert req.username == "admin"
        assert req.services == "kv,cbas"
        assert req.port == "SAME"

    def test_alias_fields(self) -> None:
        req = ClusterInitRequest(
            username="u",
            password="p",
            services="kv",
            dataPath="/data",
            cbasMemoryQuota=1024,
        )
        assert req.data_path == "/data"
        assert req.cbas_memory_quota == 1024


class TestS3LinkModel:
    def test_valid_s3_link(self) -> None:
        link = S3LinkConfig(
            region="us-east-1",
            accessKeyId="AKID",
            secretAccessKey="SECRET",
        )
        assert link.type == LinkType.S3
        assert link.region == "us-east-1"

    def test_s3_with_endpoint(self) -> None:
        link = S3LinkConfig(
            region="us-east-1",
            accessKeyId="AKID",
            secretAccessKey="SECRET",
            serviceEndpoint="http://minio:9000",
        )
        assert link.serviceEndpoint == "http://minio:9000"


class TestAzureBlobLinkModel:
    def test_requires_key_or_sas(self) -> None:
        with pytest.raises(Exception):
            AzureBlobLinkConfig(accountName="myaccount")

    def test_valid_with_account_key(self) -> None:
        link = AzureBlobLinkConfig(accountName="myaccount", accountKey="base64key==")
        assert link.accountName == "myaccount"

    def test_valid_with_sas(self) -> None:
        link = AzureBlobLinkConfig(
            accountName="myaccount",
            sharedAccessSignature="sv=2021&sig=xxx",
        )
        assert link.sharedAccessSignature is not None


class TestGCSLinkModel:
    def test_gcs_link_defaults(self) -> None:
        link = GCSLinkConfig()
        assert link.type == LinkType.GCS
        assert link.jsonCredentials is None


class TestAnalyticsQueryResponse:
    def test_empty_response(self) -> None:
        resp = AnalyticsQueryResponse(status="success")
        assert resp.results == []
        assert resp.warnings == []
        assert resp.errors == []

    def test_response_with_metrics(self) -> None:
        resp = AnalyticsQueryResponse(
            requestID="r1",
            status="success",
            results=[{"id": 1}],
            metrics=AnalyticsMetrics(
                elapsedTime="100ms",
                executionTime="80ms",
                resultCount=1,
                resultSize=20,
                warningCount=0,
                errorCount=0,
            ),
        )
        assert resp.metrics is not None
        assert resp.metrics.resultCount == 1

    def test_response_with_errors(self) -> None:
        resp = AnalyticsQueryResponse(
            status="fatal",
            errors=[AnalyticsError(code=24000, msg="Syntax error")],
        )
        assert resp.errors[0].code == 24000


# ── Exception Hierarchy ───────────────────────────────────────────────────────


class TestExceptions:
    def test_analytics_query_error_str(self) -> None:
        err = AnalyticsQueryError("Syntax error", code=24000, line=1, column=8)
        err_str = str(err)
        assert "Syntax error" in err_str
        assert "24000" in err_str
        assert "line 1" in err_str

    def test_analytics_query_error_without_location(self) -> None:
        err = AnalyticsQueryError("Runtime error", code=25000)
        assert "25000" in str(err)
        assert "line" not in str(err)

    def test_exception_hierarchy(self) -> None:
        from cb_analytics.exceptions import AnalyticsError
        assert issubclass(AnalyticsAuthError, AnalyticsError)
        assert issubclass(AnalyticsConnectionError, AnalyticsError)
        assert issubclass(AnalyticsNotFoundError, AnalyticsError)
        assert issubclass(AnalyticsRequestError, AnalyticsError)
        assert issubclass(AnalyticsServerError, AnalyticsError)
        assert issubclass(AnalyticsQueryError, AnalyticsError)

    def test_connection_error_is_retryable_marker(self) -> None:
        """AnalyticsConnectionError is what the retry logic catches."""
        err = AnalyticsConnectionError("Connection refused")
        assert isinstance(err, AnalyticsConnectionError)


# ── Config validation ─────────────────────────────────────────────────────────


class TestClientConfig:
    def test_management_url_http(self) -> None:
        from cb_analytics.config import AnalyticsClientConfig
        cfg = AnalyticsClientConfig(host="my-cluster", mgmt_port=8091, tls=False)
        assert cfg.management_url == "http://my-cluster:8091"

    def test_analytics_url_tls(self) -> None:
        from cb_analytics.config import AnalyticsClientConfig
        cfg = AnalyticsClientConfig(
            host="my-cluster", analytics_port=18095, tls=True
        )
        assert cfg.analytics_url == "https://my-cluster:18095"

    def test_invalid_port(self) -> None:
        from pydantic import ValidationError
        from cb_analytics.config import AnalyticsClientConfig
        with pytest.raises(ValidationError):
            AnalyticsClientConfig(mgmt_port=99999)
