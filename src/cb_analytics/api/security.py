# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Security & RBAC API — all credential fields use to_api_dict().

Bug fixes vs v1.0:
  - UserUpsertRequest.to_api_dict() unwraps SecretStr password
  - LdapSettings.to_api_dict() unwraps SecretStr bindPass
  - configure_auto_failover-style fix: exclude_unset preserves False
"""

from __future__ import annotations

from typing import Any

from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    AuditSettings,
    GroupInfo,
    GroupUpsertRequest,
    LdapSettings,
    NodeCertificate,
    PasswordPolicy,
    PermissionCheckRequest,
    RbacDomain,
    SamlSettings,
    SecuritySettings,
    TrustedCA,
    UserInfo,
    UserUpsertRequest,
)


class SecurityAPI:
    """Security, authentication, and authorization API."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # ── General Security ──────────────────────────────────────────────────────

    async def get_audit_settings(self) -> AuditSettings:
        """GET /settings/audit."""
        raw = await self._http.mgmt_get("/settings/audit")
        return AuditSettings.model_validate(raw)

    async def configure_audit(self, settings: AuditSettings) -> None:
        """POST /settings/audit."""
        payload = {k: v for k, v in settings.model_dump(exclude_unset=True).items()}
        await self._http.mgmt_post("/settings/audit", json=payload)

    async def get_audit_descriptors(self) -> list[dict[str, Any]]:
        """GET /settings/audit/descriptors."""
        raw = await self._http.mgmt_get("/settings/audit/descriptors")
        return raw if isinstance(raw, list) else []

    async def get_security_settings(self) -> SecuritySettings:
        """GET /settings/security."""
        raw = await self._http.mgmt_get("/settings/security")
        return SecuritySettings.model_validate(raw)

    async def update_security_settings(self, settings: SecuritySettings) -> None:
        """POST /settings/security."""
        payload = {k: v for k, v in settings.model_dump(exclude_unset=True).items()}
        await self._http.mgmt_post("/settings/security", json=payload)

    async def rotate_internal_credentials(self) -> None:
        """POST /node/controller/rotateInternalCredentials."""
        await self._http.mgmt_post("/node/controller/rotateInternalCredentials")

    async def get_response_headers_settings(self) -> dict[str, Any]:
        """GET /settings/security/responseHeaders."""
        return await self._http.mgmt_get("/settings/security/responseHeaders") or {}

    async def set_response_headers_settings(self, settings: dict[str, Any]) -> None:
        """POST /settings/security/responseHeaders."""
        await self._http.mgmt_post("/settings/security/responseHeaders", json=settings)

    async def delete_response_headers_settings(self) -> None:
        """DELETE /settings/security/responseHeaders — revert to defaults."""
        await self._http.mgmt_delete("/settings/security/responseHeaders")

    async def get_on_wire_security_settings(self, service: str | None = None) -> dict[str, Any]:
        """GET /settings/security[/{service}] — TLS cipher and protocol config."""
        path = f"/settings/security/{service}" if service else "/settings/security"
        return await self._http.mgmt_get(path) or {}

    async def set_on_wire_security_settings(self, settings: dict[str, Any], service: str | None = None) -> None:
        """POST /settings/security[/{service}]."""
        path = f"/settings/security/{service}" if service else "/settings/security"
        await self._http.mgmt_post(path, json=settings)

    # ── Authentication ────────────────────────────────────────────────────────

    async def get_ldap_settings(self) -> LdapSettings:
        """GET /settings/ldap."""
        raw = await self._http.mgmt_get("/settings/ldap")
        return LdapSettings.model_validate(raw)

    async def configure_ldap(self, settings: LdapSettings) -> None:
        """POST /settings/ldap — bindPass is unwrapped from SecretStr safely."""
        await self._http.mgmt_post("/settings/ldap", json=settings.to_api_dict())

    async def get_saml_settings(self) -> SamlSettings:
        """GET /settings/saml."""
        raw = await self._http.mgmt_get("/settings/saml")
        return SamlSettings.model_validate(raw)

    async def configure_saml(self, settings: SamlSettings) -> None:
        """POST /settings/saml."""
        payload = {k: v for k, v in settings.model_dump(exclude_unset=True).items()}
        await self._http.mgmt_post("/settings/saml", json=payload)

    async def get_saslauthd_settings(self) -> dict[str, Any]:
        """GET /settings/saslauthdAuth."""
        return await self._http.mgmt_get("/settings/saslauthdAuth") or {}

    async def configure_saslauthd(self, settings: dict[str, Any]) -> None:
        """POST /settings/saslauthdAuth."""
        await self._http.mgmt_post("/settings/saslauthdAuth", json=settings)

    async def get_password_policy(self) -> PasswordPolicy:
        """GET /settings/passwordPolicy."""
        raw = await self._http.mgmt_get("/settings/passwordPolicy")
        return PasswordPolicy.model_validate(raw)

    async def set_password_policy(self, policy: PasswordPolicy) -> None:
        """POST /settings/passwordPolicy — preserves False values correctly."""
        payload = {k: v for k, v in policy.model_dump(exclude_unset=True).items()}
        await self._http.mgmt_post("/settings/passwordPolicy", json=payload)

    async def change_password(self, new_password: str) -> None:
        """POST /controller/changePassword — change the authenticated user's password."""
        await self._http.mgmt_post("/controller/changePassword", data={"password": new_password})

    # ── Certificate Management ────────────────────────────────────────────────

    async def load_trusted_cas(self, pem_data: str) -> list[TrustedCA]:
        """POST /node/controller/loadTrustedCAs."""
        raw = await self._http.mgmt_post(
            "/node/controller/loadTrustedCAs",
            data={"certificate": pem_data},
        )
        results = raw if isinstance(raw, list) else []
        return [TrustedCA.model_validate(r) for r in results]

    async def get_trusted_cas(self) -> list[TrustedCA]:
        """GET /node/controller/loadTrustedCAs."""
        raw = await self._http.mgmt_get("/node/controller/loadTrustedCAs")
        results = raw if isinstance(raw, list) else []
        return [TrustedCA.model_validate(r) for r in results]

    async def delete_trusted_ca(self, ca_id: int) -> None:
        """DELETE /pools/default/trustedCAs/{id}."""
        await self._http.mgmt_delete(f"/pools/default/trustedCAs/{ca_id}")

    async def get_all_node_certificates(self) -> list[NodeCertificate]:
        """GET /pools/default/certificates."""
        raw = await self._http.mgmt_get("/pools/default/certificates")
        results = raw if isinstance(raw, list) else []
        return [NodeCertificate.model_validate(r) for r in results]

    async def reload_node_certificate(self) -> dict[str, Any]:
        """POST /node/controller/reloadCertificate."""
        return await self._http.mgmt_post("/node/controller/reloadCertificate") or {}

    async def get_node_certificate(self, address: str) -> NodeCertificate:
        """GET /pools/default/certificate/node/{address}."""
        raw = await self._http.mgmt_get(f"/pools/default/certificate/node/{address}")
        return NodeCertificate.model_validate(raw)

    async def regenerate_certificates(self) -> None:
        """POST /controller/regenerateCertificate."""
        await self._http.mgmt_post("/controller/regenerateCertificate")

    # ── RBAC ─────────────────────────────────────────────────────────────────

    async def list_roles(self) -> list[dict[str, Any]]:
        """GET /settings/rbac/roles."""
        raw = await self._http.mgmt_get("/settings/rbac/roles")
        return raw if isinstance(raw, list) else []

    async def list_users(self, domain: RbacDomain | None = None) -> list[UserInfo]:
        """GET /settings/rbac/users[/{domain}]."""
        path = f"/settings/rbac/users/{domain.value}" if domain else "/settings/rbac/users"
        raw = await self._http.mgmt_get(path)
        results = raw if isinstance(raw, list) else []
        return [UserInfo.model_validate(u) for u in results]

    async def get_user(self, domain: RbacDomain, username: str) -> UserInfo:
        """GET /settings/rbac/users/{domain}/{username}."""
        raw = await self._http.mgmt_get(f"/settings/rbac/users/{domain.value}/{username}")
        return UserInfo.model_validate(raw)

    async def upsert_user(self, domain: RbacDomain, username: str, request: UserUpsertRequest) -> None:
        """PUT /settings/rbac/users/{domain}/{username} — password unwrapped safely."""
        await self._http.mgmt_put(
            f"/settings/rbac/users/{domain.value}/{username}",
            data=request.to_api_dict(),
        )

    async def patch_user(self, username: str, request: UserUpsertRequest) -> None:
        """PATCH /settings/rbac/users/local/{username}."""
        await self._http.mgmt_patch(
            f"/settings/rbac/users/local/{username}",
            data=request.to_api_dict(),
        )

    async def delete_user(self, domain: RbacDomain, username: str) -> None:
        """DELETE /settings/rbac/users/{domain}/{username}."""
        await self._http.mgmt_delete(f"/settings/rbac/users/{domain.value}/{username}")

    async def list_groups(self) -> list[GroupInfo]:
        """GET /settings/rbac/groups."""
        raw = await self._http.mgmt_get("/settings/rbac/groups")
        results = raw if isinstance(raw, list) else []
        return [GroupInfo.model_validate(g) for g in results]

    async def get_group(self, groupname: str) -> GroupInfo:
        """GET /settings/rbac/groups/{groupname}."""
        raw = await self._http.mgmt_get(f"/settings/rbac/groups/{groupname}")
        return GroupInfo.model_validate(raw)

    async def upsert_group(self, groupname: str, request: GroupUpsertRequest) -> None:
        """PUT /settings/rbac/groups/{groupname}."""
        payload = {k: v for k, v in request.model_dump(by_alias=True, exclude_unset=True).items() if v is not None}
        await self._http.mgmt_put(f"/settings/rbac/groups/{groupname}", data=payload)

    async def delete_group(self, groupname: str) -> None:
        """DELETE /settings/rbac/groups/{groupname}."""
        await self._http.mgmt_delete(f"/settings/rbac/groups/{groupname}")

    async def check_permissions(self, request: PermissionCheckRequest) -> dict[str, bool]:
        """POST /pools/default/checkPermissions."""
        raw = await self._http.mgmt_post(
            "/pools/default/checkPermissions",
            data={"permissions": request.permissions},
        )
        return raw if isinstance(raw, dict) else {}

    # ── System Secrets ────────────────────────────────────────────────────────

    async def get_secrets_management_settings(self) -> dict[str, Any]:
        """GET /nodes/self/secretsManagement."""
        return await self._http.mgmt_get("/nodes/self/secretsManagement") or {}

    async def configure_secrets_management(self, settings: dict[str, Any]) -> None:
        """POST /node/controller/secretsManagement."""
        await self._http.mgmt_post("/node/controller/secretsManagement", json=settings)

    async def change_master_password(self, current: str, new: str) -> None:
        """POST /node/controller/changeMasterPassword."""
        await self._http.mgmt_post(
            "/node/controller/changeMasterPassword",
            data={"newPassword": new, "password": current},
        )

    async def rotate_data_key(self) -> None:
        """POST /node/controller/rotateDataKey."""
        await self._http.mgmt_post("/node/controller/rotateDataKey")
