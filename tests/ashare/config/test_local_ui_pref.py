"""本地 UI 偏好（QSettings）测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.config.preferences._local_ui_pref import (
    clear_local_ui_pref_cache,
    load_json_local_ui,
    load_scalar_local_ui,
    save_json_local_ui,
    user_ui_settings_key,
)
from vnpy_ashare.config.preferences._settings import get_settings


@pytest.fixture(autouse=True)
def _reset_local_ui_cache() -> None:
    clear_local_ui_pref_cache()
    yield
    clear_local_ui_pref_cache()


def test_local_ui_pref_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    rel_key = "watchlist/signal_panel_test_roundtrip"
    key = user_ui_settings_key(rel_key)
    get_settings().remove(key)

    loaded = load_json_local_ui(
        rel_key,
        load_default=lambda: {"enabled": True},
    )
    assert loaded == {"enabled": True}

    save_json_local_ui(rel_key, {"enabled": False, "symbols": ["600519.SSE"]})
    raw = get_settings().value(key)
    assert raw is not None
    assert "600519.SSE" in str(raw)

    clear_local_ui_pref_cache()
    again = load_json_local_ui(
        rel_key,
        load_default=lambda: {"enabled": True},
    )
    assert again == {"enabled": False, "symbols": ["600519.SSE"]}
    get_settings().remove(key)


def test_local_ui_pref_uses_flat_key_only(monkeypatch: pytest.MonkeyPatch) -> None:
    rel_key = "watchlist/active_group_id_test_flat"
    flat_key = user_ui_settings_key(rel_key)
    legacy_uid_key = f"ui/legacy-user/{flat_key}"
    get_settings().remove(flat_key)
    get_settings().setValue(legacy_uid_key, "group-legacy")

    value = load_scalar_local_ui(rel_key, load_default=lambda: "default")
    assert value == "default"

    get_settings().remove(legacy_uid_key)
    get_settings().remove(flat_key)
