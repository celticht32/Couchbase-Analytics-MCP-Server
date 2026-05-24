# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Unit tests for Pydantic models."""

from __future__ import annotations

from cb_analytics_mcp.couchbase.models import (
    AnalyticsQueryRequest,
    AzureBlobLinkConfig,
    CouchbaseLinkConfig,
    EncryptionLevel,
    GCSLinkConfig,
    LinkType,
    RbacDomain,
    S3LinkConfig,
    ScanConsistency,
)


class TestAnalyticsQueryRequest:
    def test_minimal_payload(self) -> None:
        req = AnalyticsQueryRequest(statement="SELECT 1")
        payload = req.to_api_payload()
        assert payload == {"statement": "SELECT 1", "timeout": "120s"}

    def test_named_args_prefixed_with_dollar(self) -> None:
        req = AnalyticsQueryRequest(statement="SELECT $id", named_args={"id": 42})
        payload = req.to_api_payload()
        assert payload["$id"] == 42
        assert "named_args" not in payload

    def test_positional_args_passed_as_args(self) -> None:
        req = AnalyticsQueryRequest(statement="SELECT $1", args=[99, "x"])
        payload = req.to_api_payload()
        assert payload["args"] == [99, "x"]

    def test_request_plus_consistency_included(self) -> None:
        req = AnalyticsQueryRequest(statement="SELECT 1", scan_consistency=ScanConsistency.REQUEST_PLUS)
        payload = req.to_api_payload()
        assert payload["scan_consistency"] == "request_plus"

    def test_not_bounded_omitted(self) -> None:
        req = AnalyticsQueryRequest(statement="SELECT 1")
        payload = req.to_api_payload()
        assert "scan_consistency" not in payload

    def test_readonly_flag(self) -> None:
        req = AnalyticsQueryRequest(statement="SELECT 1", readonly=True)
        assert req.to_api_payload()["readonly"] is True


class TestS3LinkConfig:
    def test_secrets_not_in_repr(self) -> None:
        cfg = S3LinkConfig(
            region="us-east-1",
            accessKeyId="AKIAEXAMPLE",
            secretAccessKey="secret-value",
        )
        assert "AKIAEXAMPLE" not in repr(cfg)
        assert "secret-value" not in repr(cfg)

    def test_to_api_dict_unwraps_secrets(self) -> None:
        cfg = S3LinkConfig(
            region="us-east-1",
            accessKeyId="AKIAEXAMPLE",
            secretAccessKey="secret-value",
        )
        out = cfg.to_api_dict()
        assert out["accessKeyId"] == "AKIAEXAMPLE"
        assert out["secretAccessKey"] == "secret-value"
        assert out["type"] == "s3"

    def test_optional_session_token(self) -> None:
        cfg = S3LinkConfig(
            region="eu-west-1",
            accessKeyId="K",
            secretAccessKey="S",
            sessionToken="STS-TOKEN",
        )
        assert cfg.to_api_dict()["sessionToken"] == "STS-TOKEN"


class TestAzureBlobLinkConfig:
    def test_account_key_unwrapped(self) -> None:
        cfg = AzureBlobLinkConfig(accountName="acc", accountKey="base64key")
        out = cfg.to_api_dict()
        assert out["accountName"] == "acc"
        assert out["accountKey"] == "base64key"

    def test_sas_alternative(self) -> None:
        cfg = AzureBlobLinkConfig(accountName="acc", sharedAccessSignature="sas")
        out = cfg.to_api_dict()
        assert out["sharedAccessSignature"] == "sas"
        assert "accountKey" not in out


class TestGCSLinkConfig:
    def test_json_credentials(self) -> None:
        creds = '{"type":"service_account"}'
        cfg = GCSLinkConfig(jsonCredentials=creds)
        assert cfg.to_api_dict()["jsonCredentials"] == creds

    def test_application_default(self) -> None:
        cfg = GCSLinkConfig(applicationDefaultCredentials=True)
        out = cfg.to_api_dict()
        assert out["applicationDefaultCredentials"] is True


class TestCouchbaseLinkConfig:
    def test_password_unwrapped(self) -> None:
        cfg = CouchbaseLinkConfig(hostname="h", username="u", password="p", encryption=EncryptionLevel.FULL)
        out = cfg.to_api_dict()
        assert out["password"] == "p"
        assert out["encryption"] == "full"

    def test_password_not_in_repr(self) -> None:
        cfg = CouchbaseLinkConfig(hostname="h", username="u", password="p")
        assert "p" not in repr(cfg.password)
        assert "secret" in repr(cfg.password).lower() or "***" in repr(cfg.password)


class TestEnums:
    def test_scan_consistency_str_value(self) -> None:
        assert ScanConsistency.REQUEST_PLUS == "request_plus"
        assert ScanConsistency("request_plus") == ScanConsistency.REQUEST_PLUS

    def test_link_type(self) -> None:
        assert LinkType.S3 == "s3"
        assert LinkType("couchbase") == LinkType.COUCHBASE

    def test_rbac_domain(self) -> None:
        assert RbacDomain.LOCAL == "local"
