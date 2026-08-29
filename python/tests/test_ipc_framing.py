"""IPC framing / MessagePack 编解码单元测试。"""

from __future__ import annotations

import io
import unittest

from dingda_sidecar.runtime.ipc_framing import encode_message, read_frame, write_frame


class IpcFramingTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        msg = {"type": "request", "id": 1, "method": "runtime.ping", "params": {}}
        buf = io.BytesIO()
        write_frame(buf, msg)
        buf.seek(0)
        decoded = read_frame(buf)
        self.assertEqual(decoded, msg)

    def test_encode_has_length_prefix(self) -> None:
        raw = encode_message({"type": "event", "method": "runtime.ready", "params": {}})
        self.assertGreaterEqual(len(raw), 5)
        length = int.from_bytes(raw[:4], "big")
        self.assertEqual(length, len(raw) - 4)


if __name__ == "__main__":
    unittest.main()
