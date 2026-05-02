# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""API module — one class per documented API group."""

from cb_analytics.api.analytics import (
    AnalyticsAdminAPI,
    AnalyticsConfigAPI,
    AnalyticsLinksAPI,
    AnalyticsServiceAPI,
    AnalyticsSettingsAPI,
)
from cb_analytics.api.cluster import ClusterAPI
from cb_analytics.api.security import SecurityAPI
from cb_analytics.api.server_groups import ServerGroupsAPI

__all__ = [
    "ClusterAPI",
    "AnalyticsServiceAPI",
    "AnalyticsAdminAPI",
    "AnalyticsConfigAPI",
    "AnalyticsSettingsAPI",
    "AnalyticsLinksAPI",
    "SecurityAPI",
    "ServerGroupsAPI",
]
