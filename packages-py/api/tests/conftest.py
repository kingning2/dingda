"""pytest 全局 fixtures。"""

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _reset_shared_browser_manager():
    """隔离进程级浏览器单例：应用 lifespan 关闭会 stop 掉共享池。

    有测试用 ``with TestClient(create_app())`` 触发 shutdown，会把全局
    ``get_browser_manager()`` 停掉；同一进程内不重置会污染后续用例
    （如调用未 mock 管理器的 ``call_tool``）。
    """
    yield
    import browser.manager as browser_manager

    browser_manager._shared = None
