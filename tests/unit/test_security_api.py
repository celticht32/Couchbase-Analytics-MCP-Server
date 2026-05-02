# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Unit tests for SecurityAPI — RBAC, certs, LDAP, SAML, audit."""

from __future__ import annotations

import pytest
import respx

from cb_analytics.api.security import SecurityAPI
from cb_analytics.config import AnalyticsClientConfig
from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    AuditSettings,
    GroupUpsertRequest,
    LdapSettings,
    PasswordPolicy,
    PermissionCheckRequest,
    RbacDomain,
    SamlSettings,
    SecuritySettings,
    UserUpsertRequest,
)
from tests.conftest import MGMT_BASE, make_response, empty_response


@pytest.fixture
def security_api(config: AnalyticsClientConfig) -> SecurityAPI:
    http = HttpClient(
        management_url=MGMT_BASE,
        analytics_url="http://localhost:8095",
        username=config.username,
        password=config.password,
        timeout=10.0,
        verify_ssl=False,
        max_retries=1,
    )
    return SecurityAPI(http)


# ── Audit ─────────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_audit_settings(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/audit").mock(
        return_value=make_response({
            "auditdEnabled": True,
            "rotateInterval": 86400,
            "logPath": "/opt/couchbase/var/lib/couchbase/logs",
        })
    )
    result = await security_api.get_audit_settings()
    assert result.auditdEnabled is True
    assert result.rotateInterval == 86400


@respx.mock
@pytest.mark.asyncio
async def test_configure_audit(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/audit").mock(return_value=empty_response(200))
    await security_api.configure_audit(AuditSettings(auditdEnabled=False))


@respx.mock
@pytest.mark.asyncio
async def test_get_audit_descriptors(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/audit/descriptors").mock(
        return_value=make_response([
            {"id": 8192, "name": "login_success", "module": "ns_server"}
        ])
    )
    descriptors = await security_api.get_audit_descriptors()
    assert len(descriptors) == 1
    assert descriptors[0]["name"] == "login_success"


# ── Security Settings ─────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_security_settings(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/security").mock(
        return_value=make_response({
            "allowedHosts": ["*.example.com", "127.0.0.1"],
            "tlsMinVersion": "tlsv1.2",
        })
    )
    result = await security_api.get_security_settings()
    assert "127.0.0.1" in (result.allowedHosts or [])


@respx.mock
@pytest.mark.asyncio
async def test_update_security_settings(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/security").mock(return_value=empty_response(200))
    await security_api.update_security_settings(
        SecuritySettings(allowedHosts=["*.mycompany.com"])
    )


# ── Authentication ────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_ldap_settings(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/ldap").mock(
        return_value=make_response({
            "authenticationEnabled": True,
            "authorizationEnabled": False,
            "hosts": ["ldap.example.com"],
            "port": 389,
        })
    )
    result = await security_api.get_ldap_settings()
    assert result.authentication_enabled is True
    assert result.hosts == ["ldap.example.com"]


@respx.mock
@pytest.mark.asyncio
async def test_configure_ldap(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/ldap").mock(return_value=empty_response(200))
    await security_api.configure_ldap(
        LdapSettings(
            authenticationEnabled=True,
            hosts=["ldap.example.com"],
            port=389,
        )
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_saml_settings(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/saml").mock(
        return_value=make_response({"enabled": False, "spEntityId": "couchbase"})
    )
    result = await security_api.get_saml_settings()
    assert result.enabled is False


@respx.mock
@pytest.mark.asyncio
async def test_configure_saml(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/saml").mock(return_value=empty_response(200))
    await security_api.configure_saml(SamlSettings(enabled=True, spEntityId="my-sp"))


@respx.mock
@pytest.mark.asyncio
async def test_get_password_policy(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/passwordPolicy").mock(
        return_value=make_response({
            "minLength": 8,
            "enforceUppercase": True,
            "enforceLowercase": True,
            "enforceDigits": True,
            "enforceSpecialChars": False,
        })
    )
    policy = await security_api.get_password_policy()
    assert policy.minLength == 8
    assert policy.enforceUppercase is True


@respx.mock
@pytest.mark.asyncio
async def test_set_password_policy(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/settings/passwordPolicy").mock(return_value=empty_response(200))
    await security_api.set_password_policy(PasswordPolicy(minLength=12))


@respx.mock
@pytest.mark.asyncio
async def test_change_password(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/changePassword").mock(return_value=empty_response(200))
    await security_api.change_password("newSecret123!")


# ── Certificates ──────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_trusted_cas(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/node/controller/loadTrustedCAs").mock(
        return_value=make_response([
            {"id": 1, "subject": "CN=Root CA", "expires": "2030-01-01", "type": "generated"}
        ])
    )
    cas = await security_api.get_trusted_cas()
    assert len(cas) == 1
    assert cas[0].subject == "CN=Root CA"


@respx.mock
@pytest.mark.asyncio
async def test_delete_trusted_ca(security_api: SecurityAPI) -> None:
    respx.delete(f"{MGMT_BASE}/pools/default/trustedCAs/1").mock(
        return_value=empty_response(200)
    )
    await security_api.delete_trusted_ca(1)


@respx.mock
@pytest.mark.asyncio
async def test_get_all_node_certificates(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/pools/default/certificates").mock(
        return_value=make_response([
            {"node": "node1", "subject": "CN=node1", "expires": "2025-01-01", "type": "self-signed"}
        ])
    )
    certs = await security_api.get_all_node_certificates()
    assert certs[0].node == "node1"


@respx.mock
@pytest.mark.asyncio
async def test_regenerate_certificates(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/controller/regenerateCertificate").mock(
        return_value=empty_response(200)
    )
    await security_api.regenerate_certificates()


# ── RBAC ─────────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_list_roles(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/roles").mock(
        return_value=make_response([
            {"role": "admin", "name": "Full Admin"},
            {"role": "analytics_reader", "name": "Analytics Reader"},
        ])
    )
    roles = await security_api.list_roles()
    assert len(roles) == 2
    role_names = [r["role"] for r in roles]
    assert "analytics_reader" in role_names


@respx.mock
@pytest.mark.asyncio
async def test_list_users(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/users").mock(
        return_value=make_response([
            {"id": "alice", "domain": "local", "roles": [{"role": "admin"}]},
            {"id": "bob", "domain": "local", "roles": [{"role": "analytics_reader"}]},
        ])
    )
    users = await security_api.list_users()
    assert len(users) == 2
    assert users[0].id == "alice"


@respx.mock
@pytest.mark.asyncio
async def test_list_users_by_domain(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/users/local").mock(
        return_value=make_response([
            {"id": "alice", "domain": "local", "roles": []}
        ])
    )
    users = await security_api.list_users(domain=RbacDomain.LOCAL)
    assert all(u.domain == "local" for u in users)


@respx.mock
@pytest.mark.asyncio
async def test_get_user(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/users/local/alice").mock(
        return_value=make_response({"id": "alice", "domain": "local", "name": "Alice Smith", "roles": []})
    )
    user = await security_api.get_user(RbacDomain.LOCAL, "alice")
    assert user.id == "alice"
    assert user.name == "Alice Smith"


@respx.mock
@pytest.mark.asyncio
async def test_upsert_user(security_api: SecurityAPI) -> None:
    respx.put(f"{MGMT_BASE}/settings/rbac/users/local/carol").mock(
        return_value=empty_response(200)
    )
    await security_api.upsert_user(
        RbacDomain.LOCAL,
        "carol",
        UserUpsertRequest(password="Secret123!", roles="analytics_reader"),
    )


@respx.mock
@pytest.mark.asyncio
async def test_delete_user(security_api: SecurityAPI) -> None:
    respx.delete(f"{MGMT_BASE}/settings/rbac/users/local/alice").mock(
        return_value=empty_response(200)
    )
    await security_api.delete_user(RbacDomain.LOCAL, "alice")


@respx.mock
@pytest.mark.asyncio
async def test_list_groups(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/settings/rbac/groups").mock(
        return_value=make_response([
            {"id": "analytics-team", "description": "Analytics users", "roles": []}
        ])
    )
    groups = await security_api.list_groups()
    assert len(groups) == 1
    assert groups[0].id == "analytics-team"


@respx.mock
@pytest.mark.asyncio
async def test_upsert_group(security_api: SecurityAPI) -> None:
    respx.put(f"{MGMT_BASE}/settings/rbac/groups/analytics-team").mock(
        return_value=empty_response(200)
    )
    await security_api.upsert_group(
        "analytics-team",
        GroupUpsertRequest(description="Analytics team", roles="analytics_reader"),
    )


@respx.mock
@pytest.mark.asyncio
async def test_delete_group(security_api: SecurityAPI) -> None:
    respx.delete(f"{MGMT_BASE}/settings/rbac/groups/analytics-team").mock(
        return_value=empty_response(200)
    )
    await security_api.delete_group("analytics-team")


@respx.mock
@pytest.mark.asyncio
async def test_check_permissions(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/pools/default/checkPermissions").mock(
        return_value=make_response({
            "cluster.analytics!read": True,
            "cluster.admin!write": False,
        })
    )
    result = await security_api.check_permissions(
        PermissionCheckRequest(permissions="cluster.analytics!read,cluster.admin!write")
    )
    assert result["cluster.analytics!read"] is True
    assert result["cluster.admin!write"] is False


# ── System Secrets ────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_get_secrets_management_settings(security_api: SecurityAPI) -> None:
    respx.get(f"{MGMT_BASE}/nodes/self/secretsManagement").mock(
        return_value=make_response({"keyStorageType": "file", "keyPath": "/etc/cb/secrets"})
    )
    result = await security_api.get_secrets_management_settings()
    assert result["keyStorageType"] == "file"


@respx.mock
@pytest.mark.asyncio
async def test_rotate_data_key(security_api: SecurityAPI) -> None:
    respx.post(f"{MGMT_BASE}/node/controller/rotateDataKey").mock(
        return_value=empty_response(200)
    )
    await security_api.rotate_data_key()
