# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for Cluster, Security, and Capella API classes."""

from __future__ import annotations

import httpx
import pytest
import respx

from cb_analytics_mcp.couchbase.cluster_api import (
    CapellaClient,
    ClusterAPI,
    SecurityAPI,
)
from cb_analytics_mcp.couchbase.exceptions import (
    AnalyticsAuthError,
    AnalyticsNotFoundError,
)
from cb_analytics_mcp.couchbase.http_client import HttpClient
from cb_analytics_mcp.couchbase.models import (
    AutoFailoverSettings,
    GroupUpsertRequest,
    PermissionCheckRequest,
    RbacDomain,
    UserUpsertRequest,
)
from tests.conftest import MGMT_BASE, empty_response, make_response

CAPELLA_BASE = "https://cloudapi.cloud.couchbase.com"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def cluster(http: HttpClient) -> ClusterAPI:
    return ClusterAPI(http)


@pytest.fixture
def security(http: HttpClient) -> SecurityAPI:
    return SecurityAPI(http)


@pytest.fixture
def capella() -> CapellaClient:
    return CapellaClient(api_key_secret="test-key", timeout=2.0)


# ── ClusterAPI ────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_info(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools").mock(
        return_value=make_response({"uuid": "abc", "implementationVersion": "7.6.3"})
    )
    info = await cluster.get_cluster_info()
    assert info.uuid == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_details(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default").mock(
        return_value=make_response(
            {
                "clusterName": "MyCluster",
                "nodes": [{}, {}, {}],
                "rebalanceStatus": "none",
                "balanced": True,
                "memoryQuota": 4096,
                "cbasMemoryQuota": 2048,
            }
        )
    )
    d = await cluster.get_cluster_details()
    assert d.clusterName == "MyCluster"
    assert len(d.nodes) == 3
    assert d.memoryQuota == 4096


@respx.mock
@pytest.mark.asyncio
async def test_get_rebalance_progress_none(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/tasks").mock(return_value=make_response([]))
    p = await cluster.get_rebalance_progress()
    assert p.status == "none"


@respx.mock
@pytest.mark.asyncio
async def test_get_rebalance_progress_running(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/tasks").mock(
        return_value=make_response([{"type": "rebalance", "status": "running", "progress": 42.5}])
    )
    p = await cluster.get_rebalance_progress()
    assert p.status == "running"


@respx.mock
@pytest.mark.asyncio
async def test_auto_failover_get(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/autoFailover").mock(
        return_value=make_response({"enabled": True, "timeout": 120, "maxCount": 1})
    )
    s = await cluster.get_auto_failover_settings()
    assert s.enabled is True
    assert s.timeout == 120


@respx.mock
@pytest.mark.asyncio
async def test_auto_failover_configure(cluster: ClusterAPI) -> None:
    route = respx.post(f"{MGMT_BASE}/settings/autoFailover").mock(return_value=empty_response(200))
    await cluster.configure_auto_failover(AutoFailoverSettings(enabled=True, timeout=60, maxCount=2))
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_who_am_i(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/whoami").mock(
        return_value=make_response({"id": "Administrator", "domain": "local", "roles": [{"role": "admin"}]})
    )
    me = await cluster.who_am_i()
    assert me["id"] == "Administrator"


# ── SecurityAPI ───────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_list_users(security: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/users").mock(
        return_value=make_response(
            [{"id": "alice", "domain": "local", "roles": [{"role": "analytics_reader"}]}]
        )
    )
    users = await security.list_users()
    assert len(users) == 1
    assert users[0].id == "alice"


@respx.mock
@pytest.mark.asyncio
async def test_list_users_with_domain(security: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/users/local").mock(
        return_value=make_response([{"id": "alice", "domain": "local", "roles": []}])
    )
    users = await security.list_users(domain=RbacDomain.LOCAL)
    assert users[0].id == "alice"


@respx.mock
@pytest.mark.asyncio
async def test_upsert_user(security: SecurityAPI) -> None:
    route = respx.put(f"{MGMT_BASE}/settings/rbac/users/local/alice").mock(return_value=empty_response(200))
    await security.upsert_user(
        RbacDomain.LOCAL,
        "alice",
        UserUpsertRequest(password="p123456", roles="analytics_reader[*]", name="Alice"),
    )
    assert route.called
    body = route.calls[0].request.content.decode()
    assert "roles" in body
    assert "alice" not in body  # username is in URL, not body
    assert "analytics_reader" in body


@respx.mock
@pytest.mark.asyncio
async def test_delete_user(security: SecurityAPI) -> None:
    route = respx.delete(f"{MGMT_BASE}/settings/rbac/users/local/alice").mock(
        return_value=empty_response(200)
    )
    await security.delete_user(RbacDomain.LOCAL, "alice")
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_upsert_group(security: SecurityAPI) -> None:
    route = respx.put(f"{MGMT_BASE}/settings/rbac/groups/g1").mock(return_value=empty_response(200))
    await security.upsert_group("g1", GroupUpsertRequest(description="team", roles="analytics_reader[*]"))
    assert route.called


@respx.mock
@pytest.mark.asyncio
async def test_check_permissions(security: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/pools/default/checkPermissions").mock(
        return_value=make_response({"cluster.analytics!read": True, "cluster.admin!write": False})
    )
    result = await security.check_permissions(
        PermissionCheckRequest(permissions="cluster.analytics!read,cluster.admin!write")
    )
    assert result["cluster.analytics!read"] is True
    assert result["cluster.admin!write"] is False


@respx.mock
@pytest.mark.asyncio
async def test_list_roles(security: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/roles").mock(
        return_value=make_response(
            [{"role": "analytics_reader", "desc": "Read"}, {"role": "analytics_admin", "desc": "Admin"}]
        )
    )
    roles = await security.list_roles()
    assert len(roles) == 2


# ── CapellaClient ─────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_capella_list_organizations_data_form(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations").mock(
        return_value=make_response(
            {"data": [{"id": "org-1", "name": "Org A"}, {"id": "org-2", "name": "Org B"}]}
        )
    )
    orgs = await capella.list_organizations()
    assert len(orgs) == 2
    assert orgs[0]["name"] == "Org A"
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_list_organizations_array_form(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations").mock(
        return_value=make_response([{"id": "org-1", "name": "Org A"}])
    )
    orgs = await capella.list_organizations()
    assert len(orgs) == 1
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_401_raises_auth(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations").mock(return_value=httpx.Response(401, text="Unauthorized"))
    with pytest.raises(AnalyticsAuthError):
        await capella.list_organizations()
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_404_raises_not_found(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations/x/projects/y/clusters/z").mock(
        return_value=httpx.Response(404, text="Not found")
    )
    with pytest.raises(AnalyticsNotFoundError):
        await capella.get_cluster("x", "y", "z")
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_create_cluster(capella: CapellaClient) -> None:
    route = respx.post(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters").mock(
        return_value=make_response({"id": "cl-1", "name": "new"})
    )
    out = await capella.create_cluster("o", "p", {"name": "new"})
    assert out["id"] == "cl-1"
    assert route.called
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_delete_cluster_204(capella: CapellaClient) -> None:
    route = respx.delete(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c").mock(
        return_value=empty_response(204)
    )
    await capella.delete_cluster("o", "p", "c")
    assert route.called
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_create_backup(capella: CapellaClient) -> None:
    respx.post(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c/backups").mock(
        return_value=make_response({"id": "bk-1"})
    )
    out = await capella.create_backup("o", "p", "c")
    assert out["id"] == "bk-1"
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_restore_backup_with_target(capella: CapellaClient) -> None:
    route = respx.post(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c/backups/b/restore").mock(
        return_value=make_response({"status": "restoring"})
    )
    out = await capella.restore_backup("o", "p", "c", "b", target_cluster_id="t")
    assert out["status"] == "restoring"
    body = route.calls[0].request.content.decode()
    assert "targetClusterId" in body
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_list_api_keys(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations/o/apikeys").mock(
        return_value=make_response({"data": [{"id": "k-1", "name": "mykey"}]})
    )
    keys = await capella.list_api_keys("o")
    assert len(keys) == 1
    assert keys[0]["id"] == "k-1"
    await capella.close()


# ── ClusterAPI (missing methods) ─────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_cluster_get_tasks(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/tasks").mock(
        return_value=make_response([{"type": "rebalance", "status": "running"}])
    )
    out = await cluster.get_cluster_tasks()
    assert len(out) == 1
    assert out[0].type == "rebalance"


@respx.mock
@pytest.mark.asyncio
async def test_cluster_get_tasks_non_list(cluster: ClusterAPI) -> None:
    """API quirk — if it returns a dict instead of list, we degrade to []."""
    respx.get(f"{MGMT_BASE}/pools/default/tasks").mock(return_value=make_response({"tasks": []}))
    out = await cluster.get_cluster_tasks()
    assert out == []


@respx.mock
@pytest.mark.asyncio
async def test_cluster_rebalance_progress_running(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/tasks").mock(
        return_value=make_response(
            [
                {"type": "indexer", "status": "running"},
                {"type": "rebalance", "status": "running", "progress": 42.5},
            ]
        )
    )
    out = await cluster.get_rebalance_progress()
    assert out.status == "running"


@respx.mock
@pytest.mark.asyncio
async def test_cluster_rebalance_progress_none(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/tasks").mock(
        return_value=make_response([{"type": "indexer", "status": "running"}])
    )
    out = await cluster.get_rebalance_progress()
    assert out.status == "none"


@respx.mock
@pytest.mark.asyncio
async def test_cluster_get_auto_failover(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/autoFailover").mock(
        return_value=make_response({"enabled": True, "timeout": 120, "maxCount": 1})
    )
    out = await cluster.get_auto_failover_settings()
    assert out.enabled is True


@respx.mock
@pytest.mark.asyncio
async def test_cluster_configure_auto_failover(cluster: ClusterAPI) -> None:
    route = respx.post(f"{MGMT_BASE}/settings/autoFailover").mock(return_value=empty_response(200))
    await cluster.configure_auto_failover(AutoFailoverSettings(enabled=True, timeout=180, maxCount=2))
    assert route.called
    body = route.calls.last.request.content.decode()
    assert "enabled=true" in body
    assert "timeout=180" in body
    assert "maxCount=2" in body


@respx.mock
@pytest.mark.asyncio
async def test_cluster_get_system_events(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/events").mock(
        return_value=make_response(
            [
                {"timestamp": "2026-05-24T00:00:00Z", "severity": "info"},
            ]
        )
    )
    out = await cluster.get_system_events()
    assert len(out) == 1


@respx.mock
@pytest.mark.asyncio
async def test_cluster_get_system_events_with_filter(cluster: ClusterAPI) -> None:
    route = respx.get(f"{MGMT_BASE}/events").mock(return_value=make_response({"events": []}))
    await cluster.get_system_events(since_time="2026-01-01T00:00:00Z")
    assert "sinceTime=2026-01-01" in str(route.calls.last.request.url)


@respx.mock
@pytest.mark.asyncio
async def test_cluster_who_am_i(cluster: ClusterAPI) -> None:
    respx.get(f"{MGMT_BASE}/whoami").mock(
        return_value=make_response({"id": "Administrator", "roles": [{"role": "admin"}]})
    )
    out = await cluster.who_am_i()
    assert out["id"] == "Administrator"


@respx.mock
@pytest.mark.asyncio
async def test_cluster_who_am_i_non_dict_response(cluster: ClusterAPI) -> None:
    """Defensive: if the API hands back a non-dict, we return {}."""
    respx.get(f"{MGMT_BASE}/whoami").mock(return_value=make_response(["unexpected"]))
    out = await cluster.who_am_i()
    assert out == {}


# ── CapellaClient (status code branches) ─────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_capella_auth_error(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations").mock(
        return_value=httpx.Response(401, json={"message": "unauthorized"})
    )
    with pytest.raises(AnalyticsAuthError):
        await capella.list_organizations()
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_403_is_auth_error(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations").mock(
        return_value=httpx.Response(403, json={"message": "forbidden"})
    )
    with pytest.raises(AnalyticsAuthError):
        await capella.list_organizations()
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_404_is_not_found(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations/x/projects/y/clusters/z").mock(
        return_value=httpx.Response(404, json={"message": "no"})
    )
    with pytest.raises(AnalyticsNotFoundError):
        await capella.get_cluster("x", "y", "z")
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_4xx_other_is_request_error(capella: CapellaClient) -> None:
    from cb_analytics_mcp.couchbase.exceptions import AnalyticsRequestError

    respx.get(f"{CAPELLA_BASE}/v4/organizations").mock(
        return_value=httpx.Response(422, json={"message": "bad params"})
    )
    with pytest.raises(AnalyticsRequestError):
        await capella.list_organizations()
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_5xx_is_server_error(capella: CapellaClient) -> None:
    from cb_analytics_mcp.couchbase.exceptions import AnalyticsServerError

    respx.get(f"{CAPELLA_BASE}/v4/organizations").mock(
        return_value=httpx.Response(503, json={"message": "down"})
    )
    with pytest.raises(AnalyticsServerError):
        await capella.list_organizations()
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_list_clusters(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "c1"}, {"id": "c2"}]})
    )
    out = await capella.list_clusters("o", "p")
    assert len(out) == 2
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_create_cluster_simple(capella: CapellaClient) -> None:
    respx.post(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters").mock(
        return_value=httpx.Response(201, json={"id": "new"})
    )
    out = await capella.create_cluster("o", "p", {"name": "x"})
    assert out["id"] == "new"
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_delete_cluster(capella: CapellaClient) -> None:
    respx.delete(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c").mock(
        return_value=httpx.Response(204)
    )
    await capella.delete_cluster("o", "p", "c")
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_list_backups(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c/backups").mock(
        return_value=httpx.Response(200, json=[{"id": "b1"}])
    )
    out = await capella.list_backups("o", "p", "c")
    assert len(out) == 1
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_create_backup_simple(capella: CapellaClient) -> None:
    respx.post(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c/backups").mock(
        return_value=httpx.Response(202, json={"id": "b-new"})
    )
    out = await capella.create_backup("o", "p", "c")
    assert out["id"] == "b-new"
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_restore_in_place(capella: CapellaClient) -> None:
    respx.post(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c/backups/b/restore").mock(
        return_value=httpx.Response(202, json={"status": "restoring"})
    )
    out = await capella.restore_backup("o", "p", "c", "b")
    assert out["status"] == "restoring"
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_restore_to_target(capella: CapellaClient) -> None:
    """When target_cluster_id is set, it's posted in the body."""
    route = respx.post(f"{CAPELLA_BASE}/v4/organizations/o/projects/p/clusters/c/backups/b/restore").mock(
        return_value=httpx.Response(202, json={"status": "restoring"})
    )
    await capella.restore_backup("o", "p", "c", "b", target_cluster_id="t")
    body = route.calls.last.request.content.decode()
    assert "t" in body  # target id in payload
    await capella.close()


@respx.mock
@pytest.mark.asyncio
async def test_capella_as_list_handles_none() -> None:
    """The static helper should handle None defensively."""
    assert CapellaClient._as_list(None) == []
    assert CapellaClient._as_list("garbage") == []
    assert CapellaClient._as_list({"data": "not a list"}) == []
    assert CapellaClient._as_list([1, 2]) == [1, 2]


@respx.mock
@pytest.mark.asyncio
async def test_capella_list_api_keys_simple(capella: CapellaClient) -> None:
    respx.get(f"{CAPELLA_BASE}/v4/organizations/o/apikeys").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "k1"}]})
    )
    out = await capella.list_api_keys("o")
    assert len(out) == 1
    await capella.close()
