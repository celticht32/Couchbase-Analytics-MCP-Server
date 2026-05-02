# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Security & RBAC API implementation.

Covers all endpoints documented in the Security API section:
  - General security (audit, TLS, HSTS)
  - Authentication (LDAP, SAML, saslauthd, password policy)
  - Authorization (RBAC users, groups, roles)
  - Certificate management (trusted CAs, node certs)
  - System secrets management
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
    """
    Security, authentication, and authorization API.

    Manages RBAC users/groups/roles, TLS certificates, LDAP/SAML
    configuration, auditing, and system secrets.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    # ── General Security ──────────────────────────────────────────────────────

    async def get_audit_settings(self) -> AuditSettings:
        """GET /settings/audit — return current audit configuration."""
        raw = await self._http.mgmt_get("/settings/audit")
        return AuditSettings.model_validate(raw)

    async def configure_audit(self, settings: AuditSettings) -> None:
        """POST /settings/audit — enable/disable auditing and set options."""
        payload = {k: v for k, v in settings.model_dump().items() if v is not None}
        await self._http.mgmt_post("/settings/audit", json=payload)

    async def get_audit_descriptors(self) -> list[dict[str, Any]]:
        """GET /settings/audit/descriptors — return auditable event descriptors."""
        raw = await self._http.mgmt_get("/settings/audit/descriptors")
        return raw if isinstance(raw, list) else []

    async def get_security_settings(self) -> SecuritySettings:
        """GET /settings/security — return general security settings."""
        raw = await self._http.mgmt_get("/settings/security")
        return SecuritySettings.model_validate(raw)

    async def update_security_settings(self, settings: SecuritySettings) -> None:
        """POST /settings/security — update allowed hosts and TLS settings."""
        payload = {k: v for k, v in settings.model_dump().items() if v is not None}
        await self._http.mgmt_post("/settings/security", json=payload)

    async def rotate_internal_credentials(self) -> None:
        """POST /node/controller/rotateInternalCredentials."""
        await self._http.mgmt_post("/node/controller/rotateInternalCredentials")

    async def get_response_headers_settings(self) -> dict[str, Any]:
        """GET /settings/security/responseHeaders — HSTS and security header config."""
        return await self._http.mgmt_get("/settings/security/responseHeaders") or {}

    async def set_response_headers_settings(self, settings: dict[str, Any]) -> None:
        """POST /settings/security/responseHeaders."""
        await self._http.mgmt_post("/settings/security/responseHeaders", json=settings)

    async def delete_response_headers_settings(self) -> None:
        """DELETE /settings/security/responseHeaders — revert to defaults."""
        await self._http.mgmt_delete("/settings/security/responseHeaders")

    async def get_on_wire_security_settings(self, service: str | None = None) -> dict[str, Any]:
        """GET /settings/security[/{service}] — TLS cipher and protocol settings."""
        path = f"/settings/security/{service}" if service else "/settings/security"
        return await self._http.mgmt_get(path) or {}

    async def set_on_wire_security_settings(
        self, settings: dict[str, Any], service: str | None = None
    ) -> None:
        """POST /settings/security[/{service}]."""
        path = f"/settings/security/{service}" if service else "/settings/security"
        await self._http.mgmt_post(path, json=settings)

    # ── Authentication ────────────────────────────────────────────────────────

    async def get_ldap_settings(self) -> LdapSettings:
        """GET /settings/ldap — return LDAP authentication configuration."""
        raw = await self._http.mgmt_get("/settings/ldap")
        return LdapSettings.model_validate(raw)

    async def configure_ldap(self, settings: LdapSettings) -> None:
        """POST /settings/ldap — configure LDAP for authentication/authorization."""
        payload = {k: v for k, v in settings.model_dump(by_alias=True).items() if v is not None}
        await self._http.mgmt_post("/settings/ldap", json=payload)

    async def get_saml_settings(self) -> SamlSettings:
        """GET /settings/saml — return SAML SSO configuration."""
        raw = await self._http.mgmt_get("/settings/saml")
        return SamlSettings.model_validate(raw)

    async def configure_saml(self, settings: SamlSettings) -> None:
        """POST /settings/saml — configure SAML for SSO authentication."""
        payload = {k: v for k, v in settings.model_dump().items() if v is not None}
        await self._http.mgmt_post("/settings/saml", json=payload)

    async def get_saslauthd_settings(self) -> dict[str, Any]:
        """GET /settings/saslauthdAuth — return saslauthd configuration."""
        return await self._http.mgmt_get("/settings/saslauthdAuth") or {}

    async def configure_saslauthd(self, settings: dict[str, Any]) -> None:
        """POST /settings/saslauthdAuth."""
        await self._http.mgmt_post("/settings/saslauthdAuth", json=settings)

    async def get_password_policy(self) -> PasswordPolicy:
        """GET /settings/passwordPolicy."""
        raw = await self._http.mgmt_get("/settings/passwordPolicy")
        return PasswordPolicy.model_validate(raw)

    async def set_password_policy(self, policy: PasswordPolicy) -> None:
        """POST /settings/passwordPolicy."""
        payload = {k: v for k, v in policy.model_dump().items() if v is not None}
        await self._http.mgmt_post("/settings/passwordPolicy", json=payload)

    async def change_password(self, password: str) -> None:
        """POST /controller/changePassword — change the authenticated user's password."""
        await self._http.mgmt_post("/controller/changePassword", data={"password": password})

    # ── Certificate Management ────────────────────────────────────────────────

    async def load_trusted_cas(self, pem_data: str) -> list[TrustedCA]:
        """POST /node/controller/loadTrustedCAs — upload root CA certificates."""
        raw = await self._http.mgmt_post(
            "/node/controller/loadTrustedCAs",
            data={"certificate": pem_data},
        )
        results = raw if isinstance(raw, list) else []
        return [TrustedCA.model_validate(r) for r in results]

    async def get_trusted_cas(self) -> list[TrustedCA]:
        """GET /node/controller/loadTrustedCAs — list trusted root certificates."""
        raw = await self._http.mgmt_get("/node/controller/loadTrustedCAs")
        results = raw if isinstance(raw, list) else []
        return [TrustedCA.model_validate(r) for r in results]

    async def delete_trusted_ca(self, ca_id: int) -> None:
        """DELETE /pools/default/trustedCAs/{id}."""
        await self._http.mgmt_delete(f"/pools/default/trustedCAs/{ca_id}")

    async def get_all_node_certificates(self) -> list[NodeCertificate]:
        """GET /pools/default/certificates — retrieve certificates for all nodes."""
        raw = await self._http.mgmt_get("/pools/default/certificates")
        results = raw if isinstance(raw, list) else []
        return [NodeCertificate.model_validate(r) for r in results]

    async def upload_node_certificate(self) -> dict[str, Any]:
        """POST /node/controller/reloadCertificate — upload and reload node cert."""
        return await self._http.mgmt_post("/node/controller/reloadCertificate") or {}

    async def get_node_certificate(self, address: str) -> NodeCertificate:
        """GET /pools/default/certificate/node/{address}."""
        raw = await self._http.mgmt_get(f"/pools/default/certificate/node/{address}")
        return NodeCertificate.model_validate(raw)

    async def regenerate_certificates(self) -> None:
        """POST /controller/regenerateCertificate — regenerate all node certificates."""
        await self._http.mgmt_post("/controller/regenerateCertificate")

    # ── Authorization (RBAC) ──────────────────────────────────────────────────

    async def list_roles(self) -> list[dict[str, Any]]:
        """GET /settings/rbac/roles — list all available roles."""
        raw = await self._http.mgmt_get("/settings/rbac/roles")
        return raw if isinstance(raw, list) else []

    async def list_users(self, domain: RbacDomain | None = None) -> list[UserInfo]:
        """
        GET /settings/rbac/users[/{domain}]

        List all users. Optionally filter by domain (local or external).
        """
        path = f"/settings/rbac/users/{domain.value}" if domain else "/settings/rbac/users"
        raw = await self._http.mgmt_get(path)
        results = raw if isinstance(raw, list) else []
        return [UserInfo.model_validate(u) for u in results]

    async def get_user(self, domain: RbacDomain, username: str) -> UserInfo:
        """GET /settings/rbac/users/{domain}/{username}."""
        raw = await self._http.mgmt_get(f"/settings/rbac/users/{domain.value}/{username}")
        return UserInfo.model_validate(raw)

    async def upsert_user(
        self,
        domain: RbacDomain,
        username: str,
        request: UserUpsertRequest,
    ) -> None:
        """
        PUT /settings/rbac/users/{domain}/{username}

        Create or replace a user with the given roles and optional group memberships.
        """
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        await self._http.mgmt_put(
            f"/settings/rbac/users/{domain.value}/{username}",
            data=payload,
        )

    async def patch_user(
        self,
        username: str,
        request: UserUpsertRequest,
    ) -> None:
        """
        PATCH /settings/rbac/users/local/{username}

        Partially update a local user (e.g., add roles without replacing all).
        """
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        await self._http.mgmt_patch(
            f"/settings/rbac/users/local/{username}",
            data=payload,
        )

    async def delete_user(self, domain: RbacDomain, username: str) -> None:
        """DELETE /settings/rbac/users/{domain}/{username}."""
        await self._http.mgmt_delete(f"/settings/rbac/users/{domain.value}/{username}")

    async def list_groups(self) -> list[GroupInfo]:
        """GET /settings/rbac/groups — list all RBAC groups."""
        raw = await self._http.mgmt_get("/settings/rbac/groups")
        results = raw if isinstance(raw, list) else []
        return [GroupInfo.model_validate(g) for g in results]

    async def get_group(self, groupname: str) -> GroupInfo:
        """GET /settings/rbac/groups/{groupname}."""
        raw = await self._http.mgmt_get(f"/settings/rbac/groups/{groupname}")
        return GroupInfo.model_validate(raw)

    async def upsert_group(self, groupname: str, request: GroupUpsertRequest) -> None:
        """PUT /settings/rbac/groups/{groupname} — create or replace a group."""
        payload = {k: v for k, v in request.model_dump(by_alias=True).items() if v is not None}
        await self._http.mgmt_put(f"/settings/rbac/groups/{groupname}", data=payload)

    async def delete_group(self, groupname: str) -> None:
        """DELETE /settings/rbac/groups/{groupname}."""
        await self._http.mgmt_delete(f"/settings/rbac/groups/{groupname}")

    async def check_permissions(self, request: PermissionCheckRequest) -> dict[str, bool]:
        """
        POST /pools/default/checkPermissions

        Check whether the current user has the specified permissions.
        Returns a dict mapping permission string → bool.
        """
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
