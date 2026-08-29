"""Auto-generated from contracts/schema."""

from __future__ import annotations

from typing import TypedDict


class PluginEventProgress(TypedDict):
    plugin_id: str
    received_bytes: int
    total_bytes: int
    file_name: str


class PluginIpcInstallRequest(TypedDict):
    plugin_id: str


class PluginIpcInstallResponse(TypedDict):
    item: PluginItem


class PluginIpcListResponse(TypedDict):
    items: list[PluginItem]


class PluginIpcUninstallRequest(TypedDict):
    plugin_id: str


class PluginIpcUninstallResponse(TypedDict):
    item: PluginItem


class PluginItem(TypedDict, total=False):
    id: str
    name: str
    description: str
    status: str
    error: str
