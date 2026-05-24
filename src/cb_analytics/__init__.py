# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""
cb_analytics — Python SDK, CLI, and TUI for Couchbase Enterprise Analytics
and Capella Analytics REST APIs.

Copyright (c) 2026 Chris Ahrendt. MIT License.
"""

__version__ = "1.1.0"
__author__ = "Chris Ahrendt"
__license__ = "MIT"

__all__ = ["AnalyticsClient", "AnalyticsClientConfig"]

from cb_analytics.client import AnalyticsClient
from cb_analytics.config import AnalyticsClientConfig

# Create a py.typed marker (inline)
