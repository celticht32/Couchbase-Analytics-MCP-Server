# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""
cb_analytics — Python SDK for Couchbase Enterprise Analytics REST API.

Covers all documented API groups:
  - Cluster & Nodes (initialization, rebalance, failover, settings)
  - Analytics Service (query execution, admin, config, settings)
  - Analytics Links (create, read, update, delete)
  - Security & RBAC (users, groups, roles, certificates, LDAP, SAML)
  - Server Groups
  - Statistics & Logging
"""

__version__ = "1.0.0"
__all__ = ["AnalyticsClient", "AnalyticsClientConfig"]

from cb_analytics.client import AnalyticsClient, AnalyticsClientConfig
