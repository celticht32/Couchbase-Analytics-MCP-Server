# Copyright (c) 2026 Chris Ahrendt
# SPDX-License-Identifier: MIT
"""Server Group Awareness API."""

from __future__ import annotations

from cb_analytics.http_client import HttpClient
from cb_analytics.models import (
    ServerGroupCreateRequest,
    ServerGroupInfo,
    ServerGroupMembershipUpdate,
    ServerGroupsResponse,
    ServerGroupUpdateRequest,
)


class ServerGroupsAPI:
    """REST API for Server Group Awareness management."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def get_groups(self) -> ServerGroupsResponse:
        """GET /pools/default/serverGroups."""
        raw = await self._http.mgmt_get("/pools/default/serverGroups")
        return ServerGroupsResponse.model_validate(raw)

    async def create_group(self, request: ServerGroupCreateRequest) -> ServerGroupInfo:
        """POST /pools/default/serverGroups."""
        raw = await self._http.mgmt_post("/pools/default/serverGroups", data={"name": request.name})
        return ServerGroupInfo.model_validate(raw or {"name": request.name})

    async def add_node_to_group(self, uuid: str, otp_node: str) -> None:
        """POST /pools/default/serverGroups/{uuid}/addNode."""
        await self._http.mgmt_post(f"/pools/default/serverGroups/{uuid}/addNode", data={"otpNode": otp_node})

    async def rename_group(self, uuid: str, request: ServerGroupUpdateRequest) -> None:
        """PUT /pools/default/serverGroups/{uuid}."""
        await self._http.mgmt_put(f"/pools/default/serverGroups/{uuid}", data={"name": request.name})

    async def update_group_membership(self, rev: int, update: ServerGroupMembershipUpdate) -> None:
        """PUT /pools/default/serverGroups?rev={rev}."""
        await self._http.mgmt_put("/pools/default/serverGroups", json=update.model_dump(), params={"rev": rev})

    async def delete_group(self, uuid: str) -> None:
        """DELETE /pools/default/serverGroups/{uuid}."""
        await self._http.mgmt_delete(f"/pools/default/serverGroups/{uuid}")
