"""第三方 bootstrap 测试。"""

from src.adapters.bootstrap import ensure_third_party_path, third_party_root


def test_third_party_root_exists() -> None:
    assert third_party_root().is_dir()


def test_ensure_third_party_path_idempotent() -> None:
    path = ensure_third_party_path()
    assert path == ensure_third_party_path()
