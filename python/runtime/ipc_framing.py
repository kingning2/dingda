"""IPC 帧编解码 — `[u32 BE length][MessagePack payload]`。"""

from __future__ import annotations

import struct
from typing import Any, BinaryIO

import msgpack

_MAX_FRAME = 16 * 1024 * 1024


def encode_message(message: dict[str, Any]) -> bytes:
    payload = msgpack.packb(message, use_bin_type=True)
    assert payload is not None
    return struct.pack(">I", len(payload)) + payload


def read_frame(reader: BinaryIO) -> dict[str, Any] | None:
    """读一帧；对端关闭返回 None。"""
    header = _read_exact(reader, 4)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    if length > _MAX_FRAME:
        raise ValueError(f"frame length {length} exceeds limit")
    payload = _read_exact(reader, length)
    if payload is None:
        return None
    decoded = msgpack.unpackb(payload, raw=False)
    if not isinstance(decoded, dict):
        raise ValueError("IPC frame must decode to a map")
    return decoded


def write_frame(writer: BinaryIO, message: dict[str, Any]) -> None:
    writer.write(encode_message(message))
    writer.flush()


def _read_exact(reader: BinaryIO, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = reader.read(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)
