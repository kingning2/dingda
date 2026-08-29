"""Auto-generated from contracts/schema."""

from __future__ import annotations

from typing import TypedDict


class ChannelAccount(TypedDict):
    id: str
    kind: str
    name: str
    credential: str
    enabled: bool


class ChannelAli1688SearchOffer(TypedDict, total=False):
    offerId: str
    title: str
    price: str
    supplier: str
    location: str
    tags: list[str]
    turnover: str
    isP4P: bool
    url: str
    image: str


class ChannelConversation(TypedDict, total=False):
    id: str
    account_id: str
    cid: str
    peer_id: str
    peer_name: str
    item_id: str
    item_title: str
    item_price: int
    updated_at: str


class ChannelCookie(TypedDict, total=False):
    name: str
    value: str
    domain: str
    path: str
    expires: float
    httpOnly: bool
    secure: bool
    sameSite: str


class ChannelEventMessage(TypedDict, total=False):
    account_id: str
    message: ChannelMessage
    suggestion: str


class ChannelEventStatus(TypedDict, total=False):
    account_id: str
    state: str
    detail: str


class ChannelIpcCloseSiteRequest(TypedDict, total=False):
    account_id: str


class ChannelIpcCloseSiteResponse(TypedDict):
    ok: bool


class ChannelIpcConnectRequest(TypedDict):
    account_id: str


class ChannelIpcConnectResponse(TypedDict, total=False):
    ok: bool
    state: str
    detail: str


class ChannelIpcDisconnectRequest(TypedDict):
    account_id: str


class ChannelIpcDisconnectResponse(TypedDict):
    ok: bool


class ChannelIpcOpenSiteRequest(TypedDict):
    account_id: str
    x: float
    y: float
    width: float
    height: float


class ChannelIpcOpenSiteResponse(TypedDict, total=False):
    ok: bool
    detail: str


class ChannelIpcQrCancelRequest(TypedDict):
    session_id: str


class ChannelIpcQrCancelResponse(TypedDict, total=False):
    ok: bool
    detail: str


class ChannelIpcQrCheckRequest(TypedDict):
    session_id: str


class ChannelIpcQrCheckResponse(TypedDict, total=False):
    ok: bool
    status: str
    session_id: str
    cookies: list[ChannelCookie]
    detail: str
    qr_base64: str


class ChannelIpcQrStartRequest(TypedDict, total=False):
    account_id: str
    name: str
    kind: str


class ChannelIpcQrStartResponse(TypedDict, total=False):
    ok: bool
    status: str
    session_id: str
    qr_base64: str
    detail: str


class ChannelIpcSendRequest(TypedDict):
    conversation_id: str
    content: str


class ChannelIpcSendResponse(TypedDict, total=False):
    ok: bool
    message_id: str
    detail: str


class ChannelIpcStateRequest(TypedDict):
    accounts: list[ChannelAccount]
    settings: ChannelSettings


class ChannelIpcStateResponse(TypedDict):
    accounts: list[ChannelAccount]
    conversations: list[ChannelConversation]
    messages: list[ChannelMessage]
    settings: ChannelSettings


class ChannelMessage(TypedDict):
    id: str
    conversation_id: str
    direction: str
    sender: str
    content: str
    created_at: str


class ChannelSettings(TypedDict):
    auto_reply: bool


class ChannelSidecarCookieRenewRequest(TypedDict, total=False):
    account_id: str
    cookies: list[ChannelCookie]
    punish_url: str
    trace_id: str


class ChannelSidecarCookieRenewResponse(TypedDict, total=False):
    ok: bool
    status: str
    cookies: list[ChannelCookie]
    detail: str
    trace_id: str


class ChannelSidecarLoginProbeRequest(TypedDict, total=False):
    account_id: str
    cookies: list[ChannelCookie]
    headed: bool
    platform: str
    trace_id: str


class ChannelSidecarLoginProbeResponse(TypedDict, total=False):
    ok: bool
    online: bool
    status: str
    final_url: str
    detail: str
    trace_id: str
    cookies: list[ChannelCookie]


class ChannelSidecarQrCancelRequest(TypedDict, total=False):
    session_id: str
    trace_id: str
    platform: str


class ChannelSidecarQrCancelResponse(TypedDict, total=False):
    ok: bool
    detail: str
    trace_id: str


class ChannelSidecarQrCheckRequest(TypedDict, total=False):
    session_id: str
    trace_id: str
    platform: str


class ChannelSidecarQrCheckResponse(TypedDict, total=False):
    ok: bool
    status: str
    session_id: str
    cookies: list[ChannelCookie]
    detail: str
    qr_base64: str
    trace_id: str


class ChannelSidecarQrStartRequest(TypedDict, total=False):
    account_id: str
    trace_id: str
    platform: str


class ChannelSidecarQrStartResponse(TypedDict, total=False):
    ok: bool
    status: str
    session_id: str
    qr_base64: str
    detail: str
    trace_id: str


class ChannelSidecarSearchRequest(TypedDict, total=False):
    account_id: str
    keyword: str
    cookies: list[ChannelCookie]
    max_results: int
    headed: bool
    platform: str
    trace_id: str


class ChannelSidecarSearchResponse(TypedDict, total=False):
    ok: bool
    status: str
    keyword: str
    total: int
    total_before_filter: int
    offers: list[str]
    final_url: str
    detail: str
    trace_id: str


class ChannelXianyuSearchItem(TypedDict, total=False):
    itemId: str
    title: str
    url: str
    image: str
    price: str
    location: str
    seller: str
    wantCount: str
    publishedAt: str
    tags: list[str]
