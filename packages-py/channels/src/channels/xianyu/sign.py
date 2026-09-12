"""闲鱼 mtop 签名与 IM 辅助算法。

职责：
    经 execjs 桥接 static/goofish_js_version_2.js，提供 generate_sign、generate_device_id 等；
    供 session、mtop、ws 使用。

设计说明：
    - JS 资产在本包 static/，不依赖 goofish_cli 包路径
"""

from __future__ import annotations

import subprocess
from functools import lru_cache, partial
from pathlib import Path

import execjs
import execjs._external_runtime

# pyexecjs 保存了自己的 Popen；只修补该引用，避免污染全进程 subprocess.Popen。
execjs._external_runtime.Popen = partial(subprocess.Popen, encoding="utf-8")

_JS_PATH = Path(__file__).resolve().parent / "static" / "goofish_js_version_2.js"


@lru_cache(maxsize=1)
def _ctx() -> execjs._abstract_runtime.AbstractRuntimeContext:
    return execjs.compile(_JS_PATH.read_text(encoding="utf-8"))


def generate_sign(t: str, token: str, data: str) -> str:
    return _ctx().call("generate_sign", t, token, data)


def generate_device_id(user_id: str) -> str:
    return _ctx().call("generate_device_id", user_id)


def generate_mid() -> str:
    return _ctx().call("generate_mid")


def generate_uuid() -> str:
    return _ctx().call("generate_uuid")


def decrypt(data: str) -> str:
    return _ctx().call("decrypt", data)
