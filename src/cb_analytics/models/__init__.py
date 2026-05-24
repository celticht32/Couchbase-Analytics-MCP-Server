# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
Pydantic v2 models for all Couchbase Enterprise Analytics REST API
request bodies and response shapes.

Security note: credentials (passwords, secret keys) use SecretStr so
they never appear in repr(), logs, or serialized output. Call
.get_secret_value() only at the HTTP serialization boundary.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, model_validator


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
    password: SecretStr
    data_path: str | None = Field(None, alias="dataPath")
    analytics_path: str | None = Field(None, alias="analyticsPath")
    java_home: str | None = Field(None, alias="javaHome")
    send_stats: bool = Field(True, alias="sendStats")
    cluster_name: str | None = Field(None, alias="clusterName")
    services: str
    memory_quota: int | None = Field(None, alias="memoryQuota")
    cbas_memory_quota: int | None = Field(None, alias="cbasMemoryQuota")
    afamily: AddressFamily = AddressFamily.IPV4
    afamily_only: bool = Field(False, alias="afamilyOnly")
    node_encryption: NodeEncryption = Field(NodeEncryption.OFF, alias="nodeEncryption")
    indexer_storage_mode: IndexerStorageMode = Field(IndexerStorageMode.PLASMA, alias="indexerStorageMode")
    port: str = "SAME"
    allowed_hosts: str | None = Field(None, alias="allowedHosts")
    model_config = {"populate_by_name": True}

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize for HTTP, unwrapping SecretStr values."""
        d = {k: v for k, v in self.model_dump(by_alias=True).items() if v is not None}
        if self.password:
            d["password"] = self.password.get_secret_value()
        return d

class ClusterInitResponse(BaseModel):
    new_base_uri: str = Field(alias="newBaseUri")
    model_config = {"populate_by_name": True}

class NodeInitRequest(BaseModel):
    path: str
    index_path: str | None = Field(None, alias="indexPath")
    cbas_path: str | None = Field(None, alias="cbasPath")
    model_config = {"populate_by_name": True}

class CredentialsRequest(BaseModel):
    username: str
    password: SecretStr
    port: str = "SAME"

    def to_api_dict(self) -> dict[str, Any]:
        return {"username": self.username, "password": self.password.get_secret_value(), "port": self.port}

class RenameNodeRequest(BaseModel):
    hostname: str

class MemoryConfigRequest(BaseModel):
    memory_quota: int | None = Field(None, alias="memoryQuota")
    cbas_memory_quota: int | None = Field(None, alias="cbasMemoryQuota")
    cluster_name: str | None = Field(None, alias="clusterName")
    model_config = {"populate_by_name": True}

class SetupServicesRequest(BaseModel):
    services: str

class AddNodeRequest(BaseModel):
    hostname: str
    user: str
    password: SecretStr
    services: str

    def to_api_dict(self) -> dict[str, Any]:
        return {"hostname": self.hostname, "user": self.user,
                "password": self.password.get_secret_value(), "services": self.services}

class EjectNodeRequest(BaseModel):
    otpNode: str

class RebalanceRequest(BaseModel):
    known_nodes: str = Field(alias="knownNodes")
    ejected_nodes: str | None = Field(None, alias="ejectedNodes")
    model_config = {"populate_by_name": True}

class RebalanceRetryConfig(BaseModel):
    enabled: bool | None = None
    afterTimePeriod: int | None = None
    maxAttempts: int | None = None

class RebalanceProgress(BaseModel):
    status: str
    rawProgress: dict[str, Any] | None = None

class FailoverRequest(BaseModel):
    otpNode: str
    allowUnsafe: bool | None = None

class AutoFailoverSettings(BaseModel):
    enabled: bool | None = None
    timeout: int | None = None
    maxCount: int | None = None
    failoverOnDataDiskIssues: dict[str, Any] | None = None
    failoverServerGroup: bool | None = None

class RecoveryTypeRequest(BaseModel):
    otpNode: str
    recoveryType: RecoveryType

class AlertSettings(BaseModel):
    enabled: bool | None = None
    emailServer: dict[str, Any] | None = None
    recipients: list[str] | None = None
    sender: str | None = None
    alerts: list[str] | None = None
    pop: dict[str, Any] | None = None

class ClusterInfo(BaseModel):
    pools: list[dict[str, Any]] = Field(default_factory=list)
    isAdminCreds: bool | None = None
    uuid: str | None = None
    implementationVersion: str | None = None
    componentsVersion: dict[str, str] | None = None

class PoolsDefault(BaseModel):
    name: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    rebalanceStatus: str | None = None
    balanced: bool | None = None
    clusterName: str | None = None
    memoryQuota: int | None = None
    cbasMemoryQuota: int | None = None
    model_config = {"extra": "allow"}

class NodeInfo(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    model_config = {"extra": "allow"}

class NodeServices(BaseModel):
    rev: int | None = None
    nodesExt: list[dict[str, Any]] = Field(default_factory=list)
    clusterCapabilities: dict[str, Any] | None = None

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
    nodes: str = "*"
    logRedactionLevel: str | None = None
    logRedactionSalt: str | None = None
    uploadHost: str | None = None
    customer: str | None = None
    ticket: str | None = None

class StatsSingleResponse(BaseModel):
    data: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] | None = None
    startTimestamp: int | None = None
    endTimestamp: int | None = None

class StatsMultipleRequest(BaseModel):
    specs: list[dict[str, Any]] = Field(default_factory=list)
    start: int | None = None
    end: int | None = None
    step: int | None = None
    nodes: list[str] | None = None
    alignTimestamps: bool | None = None


# ---------------------------------------------------------------------------
# Analytics query models
# ---------------------------------------------------------------------------

class AnalyticsQueryRequest(BaseModel):
    """POST/GET /api/v1/request — execute a SQL++ statement."""
    statement: str
    args: list[Any] | None = None
    named_args: dict[str, Any] | None = None
    client_context_id: str | None = None
    timeout: str | None = None
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
# Analytics Admin models
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
    authorizedNodes: list[str] | None = None
    ccRevLag: int | None = None
    state: str | None = None
    model_config = {"extra": "allow"}

class IngestionLinkState(BaseModel):
    """Per-link state within the ingestion status response."""
    name: str | None = None
    state: str | None = None
    datasetStates: list[dict[str, Any]] = Field(default_factory=list)
    pendingOperations: int | None = None
    model_config = {"extra": "allow"}

class IngestionStatus(BaseModel):
    """GET /api/v1/status/ingestion — richer shape matching actual API response."""
    links: list[IngestionLinkState] = Field(default_factory=list)
    model_config = {"extra": "allow"}

    @classmethod
    def from_raw(cls, raw: Any) -> "IngestionStatus":
        """Parse the raw response which may be a list or dict."""
        if isinstance(raw, list):
            return cls(links=[IngestionLinkState.model_validate(l) for l in raw])
        if isinstance(raw, dict):
            links_raw = raw.get("links", [])
            return cls(links=[IngestionLinkState.model_validate(l) for l in links_raw])
        return cls()


# ---------------------------------------------------------------------------
# Analytics Config models
# ---------------------------------------------------------------------------

class ServiceConfig(BaseModel):
    """GET/PUT /api/v1/config/service — only send non-None fields."""
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

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize only explicitly set (non-None) fields."""
        return {k: v for k, v in self.model_dump(exclude_unset=True).items() if v is not None}

class NodeConfig(BaseModel):
    """GET/PUT /api/v1/config/node."""
    storageBuffercacheSize: int | None = None
    storageMemorycomponentGlobalbudget: int | None = None
    model_config = {"extra": "allow"}

    def to_api_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump(exclude_unset=True).items() if v is not None}

class AnalyticsSettings(BaseModel):
    """GET/POST /settings/analytics."""
    numReplicas: int | None = None
    model_config = {"extra": "allow"}

    def to_api_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump(exclude_unset=True).items() if v is not None}


# ---------------------------------------------------------------------------
# Analytics Links models — credentials use SecretStr
# ---------------------------------------------------------------------------

class CouchbaseLinkConfig(BaseModel):
    type: Literal["couchbase"] = "couchbase"
    hostname: str
    username: str
    password: SecretStr
    encryption: EncryptionLevel = EncryptionLevel.NONE
    certificate: str | None = None
    clientCertificate: str | None = None
    clientKey: SecretStr | None = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "hostname": self.hostname,
                              "username": self.username, "password": self.password.get_secret_value(),
                              "encryption": self.encryption.value}
        if self.certificate:
            d["certificate"] = self.certificate
        if self.clientCertificate:
            d["clientCertificate"] = self.clientCertificate
        if self.clientKey:
            d["clientKey"] = self.clientKey.get_secret_value()
        return d

class S3LinkConfig(BaseModel):
    type: Literal["s3"] = "s3"
    region: str
    accessKeyId: str
    secretAccessKey: SecretStr
    sessionToken: SecretStr | None = None
    serviceEndpoint: str | None = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "region": self.region,
                              "accessKeyId": self.accessKeyId,
                              "secretAccessKey": self.secretAccessKey.get_secret_value()}
        if self.sessionToken:
            d["sessionToken"] = self.sessionToken.get_secret_value()
        if self.serviceEndpoint:
            d["serviceEndpoint"] = self.serviceEndpoint
        return d

class AzureBlobLinkConfig(BaseModel):
    type: Literal["azureblob"] = "azureblob"
    accountName: str
    accountKey: SecretStr | None = None
    sharedAccessSignature: SecretStr | None = None
    blobEndpoint: str | None = None
    endpointSuffix: str | None = None

    @model_validator(mode="after")
    def validate_credentials(self) -> "AzureBlobLinkConfig":
        if not self.accountKey and not self.sharedAccessSignature:
            raise ValueError("Either accountKey or sharedAccessSignature must be provided")
        return self

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "accountName": self.accountName}
        if self.accountKey:
            d["accountKey"] = self.accountKey.get_secret_value()
        if self.sharedAccessSignature:
            d["sharedAccessSignature"] = self.sharedAccessSignature.get_secret_value()
        if self.blobEndpoint:
            d["blobEndpoint"] = self.blobEndpoint
        if self.endpointSuffix:
            d["endpointSuffix"] = self.endpointSuffix
        return d

class GCSLinkConfig(BaseModel):
    type: Literal["gcs"] = "gcs"
    jsonCredentials: SecretStr | None = None
    applicationDefaultCredentials: str | None = None
    endpoint: str | None = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.jsonCredentials:
            d["jsonCredentials"] = self.jsonCredentials.get_secret_value()
        if self.applicationDefaultCredentials:
            d["applicationDefaultCredentials"] = self.applicationDefaultCredentials
        if self.endpoint:
            d["endpoint"] = self.endpoint
        return d

LinkConfig = CouchbaseLinkConfig | S3LinkConfig | AzureBlobLinkConfig | GCSLinkConfig

class LinkInfo(BaseModel):
    dataverse: str | None = None
    name: str | None = None
    type: str | None = None
    activeDatasets: list[str] | None = None
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Analytics Library (UDF) models
# ---------------------------------------------------------------------------

class LibraryFunction(BaseModel):
    name: str | None = None
    arity: int | None = None
    returnType: str | None = None
    args: list[str] | None = None
    model_config = {"extra": "allow"}

class LibraryInfo(BaseModel):
    scope: str | None = None
    name: str | None = None
    hash: str | None = None
    functions: list[LibraryFunction] = Field(default_factory=list)
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# RBAC / Security models
# ---------------------------------------------------------------------------

class UserUpsertRequest(BaseModel):
    password: SecretStr | None = None
    name: str | None = None
    roles: str | None = None
    groups: str | None = None

    def to_api_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.password:
            d["password"] = self.password.get_secret_value()
        if self.name:
            d["name"] = self.name
        if self.roles:
            d["roles"] = self.roles
        if self.groups:
            d["groups"] = self.groups
        return d

class UserInfo(BaseModel):
    id: str | None = None
    name: str | None = None
    domain: str | None = None
    roles: list[dict[str, Any]] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    external_groups: list[str] = Field(default_factory=list)
    model_config = {"extra": "allow"}

class GroupUpsertRequest(BaseModel):
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
    permissions: str

class LdapSettings(BaseModel):
    authentication_enabled: bool | None = Field(None, alias="authenticationEnabled")
    authorization_enabled: bool | None = Field(None, alias="authorizationEnabled")
    hosts: list[str] | None = None
    port: int | None = None
    encryption: str | None = None
    server_cert: str | None = Field(None, alias="serverCert")
    bind_dn: str | None = Field(None, alias="bindDN")
    bind_pass: SecretStr | None = Field(None, alias="bindPass")
    user_dn_mapping: str | None = Field(None, alias="userDNMapping")
    groups_query: str | None = Field(None, alias="groupsQuery")
    max_parallel_connections: int | None = Field(None, alias="maxParallelConnections")
    max_cache_size: int | None = Field(None, alias="maxCacheSize")
    cache_value_lifetime: int | None = Field(None, alias="cacheValueLifetime")
    request_timeout: int | None = Field(None, alias="requestTimeout")
    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_api_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.model_dump(by_alias=True, exclude_unset=True).items() if v is not None}
        if self.bind_pass:
            d["bindPass"] = self.bind_pass.get_secret_value()
        return d

class SamlSettings(BaseModel):
    enabled: bool | None = None
    idpMetadata: str | None = None
    idpMetadataURL: str | None = None
    spEntityId: str | None = None
    model_config = {"extra": "allow"}

class PasswordPolicy(BaseModel):
    minLength: int | None = None
    enforceUppercase: bool | None = None
    enforceLowercase: bool | None = None
    enforceDigits: bool | None = None
    enforceSpecialChars: bool | None = None

class AuditSettings(BaseModel):
    auditdEnabled: bool | None = None
    rotateInterval: int | None = None
    rotateSize: int | None = None
    logPath: str | None = None
    disabled: list[int] | None = None
    disabledUsers: list[dict[str, Any]] | None = None
    model_config = {"extra": "allow"}

class SecuritySettings(BaseModel):
    allowedHosts: list[str] | None = None
    tlsMinVersion: str | None = None
    model_config = {"extra": "allow"}

class AlternateAddressConfig(BaseModel):
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
    groups: list[dict[str, Any]] = Field(default_factory=list)
