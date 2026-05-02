# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
Pydantic v2 models for all Couchbase Enterprise Analytics REST API
request bodies and response shapes.

Grouped to match the official documentation sections:
  - Cluster & Node models
  - Analytics Service models
  - Analytics Admin models
  - Analytics Config models
  - Analytics Settings models
  - Analytics Links models
  - RBAC / Security models
  - Server Group models
  - Statistics models
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AddressFamily(str, Enum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class NodeEncryption(str, Enum):
    ON = "on"
    OFF = "off"


class IndexerStorageMode(str, Enum):
    PLASMA = "plasma"
    MAGMA = "magma"


class RecoveryType(str, Enum):
    DELTA = "delta"
    FULL = "full"


class ScanConsistency(str, Enum):
    NOT_BOUNDED = "not_bounded"
    REQUEST_PLUS = "request_plus"
    AT_PLUS = "at_plus"


class LinkType(str, Enum):
    COUCHBASE = "couchbase"
    S3 = "s3"
    AZURE_BLOB = "azureblob"
    GCS = "gcs"


class EncryptionLevel(str, Enum):
    NONE = "none"
    HALF = "half"
    FULL = "full"


class RbacDomain(str, Enum):
    LOCAL = "local"
    EXTERNAL = "external"


# ---------------------------------------------------------------------------
# Cluster / Node models
# ---------------------------------------------------------------------------


class ClusterInitRequest(BaseModel):
    """POST /clusterInit — initialize and provision a new cluster."""

    hostname: str | None = None
    username: str
    password: str
    data_path: str | None = Field(None, alias="dataPath")
    analytics_path: str | None = Field(None, alias="analyticsPath")
    java_home: str | None = Field(None, alias="javaHome")
    send_stats: bool = Field(True, alias="sendStats")
    cluster_name: str | None = Field(None, alias="clusterName")
    services: str  # comma-separated e.g. "kv,cbas"
    memory_quota: int | None = Field(None, alias="memoryQuota")
    cbas_memory_quota: int | None = Field(None, alias="cbasMemoryQuota")
    afamily: AddressFamily = AddressFamily.IPV4
    afamily_only: bool = Field(False, alias="afamilyOnly")
    node_encryption: NodeEncryption = Field(NodeEncryption.OFF, alias="nodeEncryption")
    indexer_storage_mode: IndexerStorageMode = Field(
        IndexerStorageMode.PLASMA, alias="indexerStorageMode"
    )
    port: str = "SAME"
    allowed_hosts: str | None = Field(None, alias="allowedHosts")

    model_config = {"populate_by_name": True}


class ClusterInitResponse(BaseModel):
    new_base_uri: str = Field(alias="newBaseUri")
    model_config = {"populate_by_name": True}


class NodeInitRequest(BaseModel):
    """POST /nodes/self/controller/settings — initialize node paths."""

    path: str
    index_path: str | None = Field(None, alias="indexPath")
    cbas_path: str | None = Field(None, alias="cbasPath")
    model_config = {"populate_by_name": True}


class CredentialsRequest(BaseModel):
    """POST /settings/web — establish admin credentials."""

    username: str
    password: str
    port: str = "SAME"


class RenameNodeRequest(BaseModel):
    """POST /node/controller/rename."""

    hostname: str


class MemoryConfigRequest(BaseModel):
    """POST /pools/default — configure memory quotas."""

    memory_quota: int | None = Field(None, alias="memoryQuota")
    cbas_memory_quota: int | None = Field(None, alias="cbasMemoryQuota")
    cluster_name: str | None = Field(None, alias="clusterName")
    model_config = {"populate_by_name": True}


class SetupServicesRequest(BaseModel):
    """POST /node/controller/setupServices."""

    services: str  # comma-separated: "kv,cbas"


class AddNodeRequest(BaseModel):
    """POST /controller/addNode."""

    hostname: str
    user: str
    password: str
    services: str


class EjectNodeRequest(BaseModel):
    """POST /controller/ejectNode."""

    otpNode: str


class RebalanceRequest(BaseModel):
    """POST /controller/rebalance."""

    known_nodes: str = Field(alias="knownNodes")
    ejected_nodes: str | None = Field(None, alias="ejectedNodes")
    model_config = {"populate_by_name": True}


class RebalanceRetryConfig(BaseModel):
    """GET/POST /pools/default/retryRebalance."""

    enabled: bool | None = None
    afterTimePeriod: int | None = None
    maxAttempts: int | None = None


class RebalanceProgress(BaseModel):
    status: str
    rawProgress: dict[str, Any] | None = None


class FailoverRequest(BaseModel):
    """POST /controller/failOver."""

    otpNode: str
    allowUnsafe: bool | None = None


class AutoFailoverSettings(BaseModel):
    """GET/POST /settings/autoFailover."""

    enabled: bool | None = None
    timeout: int | None = None
    maxCount: int | None = None
    failoverOnDataDiskIssues: dict[str, Any] | None = None
    failoverServerGroup: bool | None = None


class RecoveryTypeRequest(BaseModel):
    """POST /controller/setRecoveryType."""

    otpNode: str
    recoveryType: RecoveryType


class AlertSettings(BaseModel):
    """GET/POST /settings/alerts."""

    enabled: bool | None = None
    emailServer: dict[str, Any] | None = None
    recipients: list[str] | None = None
    sender: str | None = None
    alerts: list[str] | None = None
    pop: dict[str, Any] | None = None


class ClusterInfo(BaseModel):
    """Response for GET /pools."""

    pools: list[dict[str, Any]] = Field(default_factory=list)
    isAdminCreds: bool | None = None
    uuid: str | None = None
    implementationVersion: str | None = None
    componentsVersion: dict[str, str] | None = None


class PoolsDefault(BaseModel):
    """Response for GET /pools/default."""

    name: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    buckets: dict[str, Any] | None = None
    rebalanceStatus: str | None = None
    rebalanceProgressUri: str | None = None
    stopRebalanceUri: str | None = None
    balanced: bool | None = None
    clusterName: str | None = None
    memoryQuota: int | None = None
    cbasMemoryQuota: int | None = None
    model_config = {"extra": "allow"}


class NodeInfo(BaseModel):
    """Response for GET /pools/nodes."""

    nodes: list[dict[str, Any]] = Field(default_factory=list)
    model_config = {"extra": "allow"}


class NodeServices(BaseModel):
    """Response for GET /pools/default/nodeServices."""

    rev: int | None = None
    nodesExt: list[dict[str, Any]] = Field(default_factory=list)
    clusterCapabilities: dict[str, Any] | None = None
    clusterCapabilitiesVer: list[int] | None = None


class SystemEvent(BaseModel):
    timestamp: str | None = None
    component: str | None = None
    severity: str | None = None
    description: str | None = None
    node: str | None = None
    uuid: str | None = None
    model_config = {"extra": "allow"}


class ClusterTask(BaseModel):
    type: str | None = None
    status: str | None = None
    progress: float | None = None
    recommendedRefreshPeriod: float | None = None
    model_config = {"extra": "allow"}


class LogCollectionRequest(BaseModel):
    """POST /controller/startLogsCollection."""

    nodes: str = "*"
    logRedactionLevel: str | None = None
    logRedactionSalt: str | None = None
    uploadHost: str | None = None
    customer: str | None = None
    ticket: str | None = None


class StatsSingleResponse(BaseModel):
    """GET /pools/default/stats/range/{metric}."""

    data: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] | None = None
    startTimestamp: int | None = None
    endTimestamp: int | None = None


class StatsMultipleRequest(BaseModel):
    """POST /pools/default/stats/range — request multiple metrics."""

    specs: list[dict[str, Any]] = Field(default_factory=list)
    start: int | None = None
    end: int | None = None
    step: int | None = None
    nodes: list[str] | None = None
    alignTimestamps: bool | None = None


# ---------------------------------------------------------------------------
# Analytics Service models — /api/v1/request
# ---------------------------------------------------------------------------


class AnalyticsQueryRequest(BaseModel):
    """POST /api/v1/request — execute a SQL++ statement."""

    statement: str
    args: list[Any] | None = None
    named_args: dict[str, Any] | None = Field(None, alias="$parameters")
    client_context_id: str | None = Field(None, alias="client_context_id")
    timeout: str | None = None  # ISO 8601 e.g. "30s"
    scan_consistency: ScanConsistency | None = None
    read_only: bool | None = None
    pretty: bool | None = None
    max_result_size: int | None = None

    model_config = {"populate_by_name": True}


class AnalyticsMetrics(BaseModel):
    elapsedTime: str | None = None
    executionTime: str | None = None
    resultCount: int | None = None
    resultSize: int | None = None
    mutationCount: int | None = None
    sortCount: int | None = None
    warningCount: int | None = None
    errorCount: int | None = None
    processedObjects: int | None = None


class AnalyticsWarning(BaseModel):
    code: int
    msg: str


class AnalyticsError(BaseModel):
    code: int
    msg: str
    query: str | None = None
    line: int | None = None
    column: int | None = None


class AnalyticsQueryResponse(BaseModel):
    """Response from POST/GET /api/v1/request."""

    requestID: str | None = None
    clientContextID: str | None = None
    signature: dict[str, Any] | None = None
    results: list[Any] = Field(default_factory=list)
    status: str | None = None
    metrics: AnalyticsMetrics | None = None
    warnings: list[AnalyticsWarning] = Field(default_factory=list)
    errors: list[AnalyticsError] = Field(default_factory=list)
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Analytics Admin models — /api/v1/active_requests etc.
# ---------------------------------------------------------------------------


class ActiveRequest(BaseModel):
    clientContextID: str | None = None
    elapsedTime: str | None = None
    executionTime: str | None = None
    requestTime: str | None = None
    state: str | None = None
    statement: str | None = None
    userAgent: str | None = None
    model_config = {"extra": "allow"}


class CompletedRequest(BaseModel):
    clientContextID: str | None = None
    elapsedTime: str | None = None
    executionTime: str | None = None
    requestTime: str | None = None
    state: str | None = None
    statement: str | None = None
    resultCount: int | None = None
    resultSize: int | None = None
    model_config = {"extra": "allow"}


class ServiceStatus(BaseModel):
    """GET /api/v1/status/service."""

    authorizedNodes: list[str] | None = None
    ccRevLag: int | None = None
    state: str | None = None
    model_config = {"extra": "allow"}


class IngestionStatus(BaseModel):
    """GET /api/v1/status/ingestion."""

    links: list[dict[str, Any]] = Field(default_factory=list)
    model_config = {"extra": "allow"}


class CancelRequestParams(BaseModel):
    """DELETE /api/v1/active_requests — cancel by clientContextID."""

    client_context_id: str = Field(alias="client_context_id")
    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Analytics Config models — /api/v1/config/service & /api/v1/config/node
# ---------------------------------------------------------------------------


class ServiceConfig(BaseModel):
    """GET/PUT /api/v1/config/service."""

    storageBuffercacheSize: int | None = None
    storageMemorycomponentGlobalbudget: int | None = None
    activeMemoryGlobalBudget: int | None = None
    maxWebRequestSize: int | None = None
    jobHistorySize: int | None = None
    resultMaxSize: int | None = None
    resultTtl: int | None = None
    compilerSortMemorysize: int | None = None
    compilerGroupmemorysize: int | None = None
    compilerJoinmemorysize: int | None = None
    compilerParallelism: int | None = None
    model_config = {"extra": "allow"}


class NodeConfig(BaseModel):
    """GET/PUT /api/v1/config/node."""

    storageBuffercacheSize: int | None = None
    storageMemorycomponentGlobalbudget: int | None = None
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Analytics Settings models — /settings/analytics
# ---------------------------------------------------------------------------


class AnalyticsSettings(BaseModel):
    """GET/POST /settings/analytics."""

    numReplicas: int | None = None
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Analytics Links models — /api/v1/link/{name}
# ---------------------------------------------------------------------------


class CouchbaseLinkConfig(BaseModel):
    type: Literal[LinkType.COUCHBASE] = LinkType.COUCHBASE
    hostname: str
    username: str
    password: str
    encryption: EncryptionLevel = EncryptionLevel.NONE
    certificate: str | None = None
    clientCertificate: str | None = None
    clientKey: str | None = None


class S3LinkConfig(BaseModel):
    type: Literal[LinkType.S3] = LinkType.S3
    region: str
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str | None = None
    serviceEndpoint: str | None = None


class AzureBlobLinkConfig(BaseModel):
    type: Literal[LinkType.AZURE_BLOB] = LinkType.AZURE_BLOB
    accountName: str
    accountKey: str | None = None
    sharedAccessSignature: str | None = None
    blobEndpoint: str | None = None
    endpointSuffix: str | None = None

    @model_validator(mode="after")
    def validate_credentials(self) -> "AzureBlobLinkConfig":
        if not self.accountKey and not self.sharedAccessSignature:
            raise ValueError("Either accountKey or sharedAccessSignature must be provided")
        return self


class GCSLinkConfig(BaseModel):
    type: Literal[LinkType.GCS] = LinkType.GCS
    jsonCredentials: str | None = None
    applicationDefaultCredentials: str | None = None
    endpoint: str | None = None


LinkConfig = CouchbaseLinkConfig | S3LinkConfig | AzureBlobLinkConfig | GCSLinkConfig


class LinkCreateRequest(BaseModel):
    """POST /api/v1/link/{name}."""

    dataverse: str
    name: str
    config: LinkConfig = Field(discriminator="type")
    model_config = {"populate_by_name": True}


class LinkInfo(BaseModel):
    """Link details returned by GET /api/v1/link/{name}."""

    dataverse: str | None = None
    name: str | None = None
    type: str | None = None
    activeDatasets: list[str] | None = None
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# RBAC / Security models
# ---------------------------------------------------------------------------


class RoleDefinition(BaseModel):
    role: str
    bucket_name: str | None = Field(None, alias="bucketName")
    scope_name: str | None = Field(None, alias="scopeName")
    collection_name: str | None = Field(None, alias="collectionName")
    model_config = {"populate_by_name": True}


class UserUpsertRequest(BaseModel):
    """PUT/PATCH /settings/rbac/users/{domain}/{username}."""

    password: str | None = None
    name: str | None = None
    roles: str | None = None  # comma-separated role strings
    groups: str | None = None


class UserInfo(BaseModel):
    id: str | None = None
    name: str | None = None
    domain: str | None = None
    roles: list[dict[str, Any]] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    external_groups: list[str] = Field(default_factory=list)
    model_config = {"extra": "allow"}


class GroupUpsertRequest(BaseModel):
    """PUT /settings/rbac/groups/{groupname}."""

    description: str | None = None
    roles: str | None = None
    ldap_group_ref: str | None = Field(None, alias="ldapGroupRef")
    model_config = {"populate_by_name": True}


class GroupInfo(BaseModel):
    id: str | None = None
    description: str | None = None
    roles: list[dict[str, Any]] = Field(default_factory=list)
    ldap_group_ref: str | None = None
    model_config = {"extra": "allow"}


class PermissionCheckRequest(BaseModel):
    """POST /pools/default/checkPermissions."""

    permissions: str  # comma-separated permission strings


class LdapSettings(BaseModel):
    """GET/POST /settings/ldap."""

    authentication_enabled: bool | None = Field(None, alias="authenticationEnabled")
    authorization_enabled: bool | None = Field(None, alias="authorizationEnabled")
    hosts: list[str] | None = None
    port: int | None = None
    encryption: str | None = None
    server_cert: str | None = Field(None, alias="serverCert")
    bind_dn: str | None = Field(None, alias="bindDN")
    bind_pass: str | None = Field(None, alias="bindPass")
    user_dn_mapping: str | None = Field(None, alias="userDNMapping")
    groups_query: str | None = Field(None, alias="groupsQuery")
    max_parallel_connections: int | None = Field(None, alias="maxParallelConnections")
    max_cache_size: int | None = Field(None, alias="maxCacheSize")
    cache_value_lifetime: int | None = Field(None, alias="cacheValueLifetime")
    request_timeout: int | None = Field(None, alias="requestTimeout")
    model_config = {"populate_by_name": True, "extra": "allow"}


class SamlSettings(BaseModel):
    """GET/POST /settings/saml."""

    enabled: bool | None = None
    idpMetadata: str | None = None
    idpMetadataURL: str | None = None
    idpMetadataConnectAddressFamily: str | None = None
    idpMetadataTLSCAs: str | None = None
    spEntityId: str | None = None
    model_config = {"extra": "allow"}


class PasswordPolicy(BaseModel):
    """GET/POST /settings/passwordPolicy."""

    minLength: int | None = None
    enforceUppercase: bool | None = None
    enforceLowercase: bool | None = None
    enforceDigits: bool | None = None
    enforceSpecialChars: bool | None = None


class AuditSettings(BaseModel):
    """GET/POST /settings/audit."""

    auditdEnabled: bool | None = None
    rotateInterval: int | None = None
    rotateSize: int | None = None
    logPath: str | None = None
    disabled: list[int] | None = None
    disabledUsers: list[dict[str, Any]] | None = None
    model_config = {"extra": "allow"}


class SecuritySettings(BaseModel):
    """GET/POST /settings/security."""

    allowedHosts: list[str] | None = None
    tlsMinVersion: str | None = None
    model_config = {"extra": "allow"}


class AlternateAddressConfig(BaseModel):
    """PUT /node/controller/setupAlternateAddresses/external."""

    hostname: str | None = None
    mgmt: int | None = None
    mgmtSSL: int | None = None
    kv: int | None = None
    kvSSL: int | None = None
    cbas: int | None = None
    cbasSSL: int | None = None


class TrustedCA(BaseModel):
    id: int | None = None
    subject: str | None = None
    expires: str | None = None
    type: str | None = None
    pem: str | None = None
    model_config = {"extra": "allow"}


class NodeCertificate(BaseModel):
    node: str | None = None
    subject: str | None = None
    expires: str | None = None
    type: str | None = None
    pem: str | None = None
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Server Groups models
# ---------------------------------------------------------------------------


class ServerGroupInfo(BaseModel):
    name: str | None = None
    uri: str | None = None
    addNodeURI: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    model_config = {"extra": "allow"}


class ServerGroupsResponse(BaseModel):
    groups: list[ServerGroupInfo] = Field(default_factory=list)
    uri: str | None = None
    rev: int | None = None


class ServerGroupCreateRequest(BaseModel):
    name: str


class ServerGroupUpdateRequest(BaseModel):
    name: str


class ServerGroupMembershipUpdate(BaseModel):
    """PUT /pools/default/serverGroups?rev={rev}."""

    groups: list[dict[str, Any]] = Field(default_factory=list)
