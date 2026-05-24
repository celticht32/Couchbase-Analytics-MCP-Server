# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Pydantic models for Couchbase Analytics REST API.

Only the subset of the REST surface that the MCP tools actually exercise
is modelled — keeping the dependency footprint and review surface small.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

# ── Enums ──────────────────────────────────────────────────────────────────────


class ScanConsistency(StrEnum):
    NOT_BOUNDED = "not_bounded"
    REQUEST_PLUS = "request_plus"
    AT_PLUS = "at_plus"


class LinkType(StrEnum):
    COUCHBASE = "couchbase"
    S3 = "s3"
    AZUREBLOB = "azureblob"
    GCS = "gcs"


class EncryptionLevel(StrEnum):
    NONE = "none"
    HALF = "half"
    FULL = "full"


class RbacDomain(StrEnum):
    LOCAL = "local"
    EXTERNAL = "external"


# ── Query request / response ───────────────────────────────────────────────────


class AnalyticsQueryRequest(BaseModel):
    """A SQL++ statement to send to the Analytics service."""

    model_config = ConfigDict(extra="forbid")

    statement: str
    named_args: dict[str, Any] | None = None
    args: list[Any] | None = None
    scan_consistency: ScanConsistency = ScanConsistency.NOT_BOUNDED
    timeout: str = "120s"
    client_context_id: str | None = None
    pretty: bool = False
    readonly: bool = False

    def to_api_payload(self) -> dict[str, Any]:
        """Convert to the JSON body Couchbase expects."""
        payload: dict[str, Any] = {"statement": self.statement}
        if self.named_args:
            for k, v in self.named_args.items():
                payload[f"${k}"] = v
        if self.args:
            payload["args"] = self.args
        if self.scan_consistency != ScanConsistency.NOT_BOUNDED:
            payload["scan_consistency"] = self.scan_consistency.value
        if self.timeout:
            payload["timeout"] = self.timeout
        if self.client_context_id:
            payload["client_context_id"] = self.client_context_id
        if self.pretty:
            payload["pretty"] = True
        if self.readonly:
            payload["readonly"] = True
        return payload


class AnalyticsMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")
    elapsedTime: str | None = None
    executionTime: str | None = None
    resultCount: int | None = None
    resultSize: int | None = None
    warningCount: int | None = None
    errorCount: int | None = None
    processedObjects: int | None = None


class AnalyticsWarning(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: int | None = None
    msg: str | None = None


class AnalyticsErrorEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: int | None = None
    msg: str | None = None


class AnalyticsQueryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    requestID: str | None = None
    clientContextID: str | None = None
    signature: Any | None = None
    results: list[Any] = Field(default_factory=list)
    status: str | None = None
    metrics: AnalyticsMetrics | None = None
    warnings: list[AnalyticsWarning] = Field(default_factory=list)
    errors: list[AnalyticsErrorEntry] = Field(default_factory=list)


# ── Service / admin ────────────────────────────────────────────────────────────


class ServiceStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    state: str | None = None
    ccRevLag: int | None = None
    authorizedNodes: list[str] = Field(default_factory=list)


class DatasetState(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    state: str | None = None


class IngestionLinkState(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    state: str | None = None
    pendingOperations: int | None = None
    datasetStates: list[DatasetState] = Field(default_factory=list)


class IngestionStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    links: list[IngestionLinkState] = Field(default_factory=list)


class ActiveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    requestID: str | None = None
    clientContextID: str | None = None
    statement: str | None = None
    elapsedTime: str | None = None
    executionTime: str | None = None
    state: str | None = None
    users: list[str] = Field(default_factory=list)


class CompletedRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    requestID: str | None = None
    clientContextID: str | None = None
    statement: str | None = None
    elapsedTime: str | None = None
    executionTime: str | None = None
    state: str | None = None
    resultCount: int | None = None
    errorCount: int | None = None


# ── Config & settings ──────────────────────────────────────────────────────────


class ServiceConfig(BaseModel):
    """Service-level Analytics config; only commonly-tuned fields are typed."""

    model_config = ConfigDict(extra="allow")
    resultTtl: int | None = None
    compilerParallelism: int | None = None
    activeMemoryGlobalBudget: int | None = None
    storageMemorybudget: int | None = None


class AnalyticsSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    numReplicas: int = 0


# ── Links ──────────────────────────────────────────────────────────────────────


class LinkInfo(BaseModel):
    """Generic link info returned by GET /analytics/link."""

    model_config = ConfigDict(extra="ignore")
    name: str
    type: str
    dataverse: str
    activeDatasets: list[str] = Field(default_factory=list)


class S3LinkConfig(BaseModel):
    type: LinkType = LinkType.S3
    region: str
    accessKeyId: SecretStr
    secretAccessKey: SecretStr
    serviceEndpoint: str | None = None
    sessionToken: SecretStr | None = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type.value,
            "region": self.region,
            "accessKeyId": self.accessKeyId.get_secret_value(),
            "secretAccessKey": self.secretAccessKey.get_secret_value(),
        }
        if self.serviceEndpoint:
            d["serviceEndpoint"] = self.serviceEndpoint
        if self.sessionToken:
            d["sessionToken"] = self.sessionToken.get_secret_value()
        return d


class AzureBlobLinkConfig(BaseModel):
    type: LinkType = LinkType.AZUREBLOB
    accountName: str
    accountKey: SecretStr | None = None
    sharedAccessSignature: SecretStr | None = None
    endpoint: str | None = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type.value, "accountName": self.accountName}
        if self.accountKey:
            d["accountKey"] = self.accountKey.get_secret_value()
        if self.sharedAccessSignature:
            d["sharedAccessSignature"] = self.sharedAccessSignature.get_secret_value()
        if self.endpoint:
            d["endpoint"] = self.endpoint
        return d


class GCSLinkConfig(BaseModel):
    type: LinkType = LinkType.GCS
    jsonCredentials: SecretStr | None = None
    endpoint: str | None = None
    applicationDefaultCredentials: bool = False

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type.value}
        if self.jsonCredentials:
            d["jsonCredentials"] = self.jsonCredentials.get_secret_value()
        if self.endpoint:
            d["endpoint"] = self.endpoint
        if self.applicationDefaultCredentials:
            d["applicationDefaultCredentials"] = True
        return d


class CouchbaseLinkConfig(BaseModel):
    type: LinkType = LinkType.COUCHBASE
    hostname: str
    username: str
    password: SecretStr
    encryption: EncryptionLevel = EncryptionLevel.NONE
    certificate: str | None = None
    clientCertificate: str | None = None
    clientKey: SecretStr | None = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type.value,
            "hostname": self.hostname,
            "username": self.username,
            "password": self.password.get_secret_value(),
            "encryption": self.encryption.value,
        }
        if self.certificate:
            d["certificate"] = self.certificate
        if self.clientCertificate:
            d["clientCertificate"] = self.clientCertificate
        if self.clientKey:
            d["clientKey"] = self.clientKey.get_secret_value()
        return d


# ── Libraries (UDF) ────────────────────────────────────────────────────────────


class LibraryFunction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None
    arity: int | None = None


class LibraryInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    scope: str
    functions: list[LibraryFunction] = Field(default_factory=list)


# ── Security / RBAC ────────────────────────────────────────────────────────────


class UserInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    domain: str | None = None
    name: str | None = None
    roles: list[dict[str, Any]] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)


class GroupInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    description: str | None = None
    roles: list[dict[str, Any]] = Field(default_factory=list)


class UserUpsertRequest(BaseModel):
    password: SecretStr | None = None
    roles: str
    name: str | None = None


class GroupUpsertRequest(BaseModel):
    description: str | None = None
    roles: str


class PermissionCheckRequest(BaseModel):
    permissions: str


# ── Cluster ────────────────────────────────────────────────────────────────────


class ClusterInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    uuid: str | None = None
    implementationVersion: str | None = None


class ClusterDetails(BaseModel):
    model_config = ConfigDict(extra="ignore")
    clusterName: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    rebalanceStatus: str | None = None
    balanced: bool | None = None
    memoryQuota: int | None = None
    cbasMemoryQuota: int | None = None


class ClusterTask(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str | None = None
    status: str | None = None
    progress: float | None = None


class RebalanceProgress(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str | None = None


class AutoFailoverSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: bool = True
    timeout: int = 120
    maxCount: int = 1


class SystemEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    timestamp: str | None = None
    severity: str | None = None
    component: str | None = None
    description: str | None = None
