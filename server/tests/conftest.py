"""pytest 全局 fixtures。"""

import pytest
from fastapi.testclient import TestClient

from src.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
