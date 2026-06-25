"""本地 UI 偏好（QSettings）测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.config.preferences._local_ui_pref import (
    bootstrap_local_ui_prefs_from_pg,
    clear_local_ui_pref_cache,
    load_json_local_ui,
    purge_ui_prefs_from_pg,
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
    monkeypatch.setattr(
        "vnpy_ashare.config.preferences._local_ui_pref.get_user_id",
        lambda: "user-test-roundtrip",
    )
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


def test_local_ui_pref_user_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    import vnpy_ashare.config.preferences._local_ui_pref as mod

    rel_key = "watchlist/active_group_id_test_isolation"
    monkeypatch.setattr(mod, "get_user_id", lambda: "user-a")
    save_json_local_ui(rel_key, "group-a")
    clear_local_ui_pref_cache()

    monkeypatch.setattr(mod, "get_user_id", lambda: "user-b")
    value = load_json_local_ui(
        rel_key,
        load_default=lambda: "default",
    )
    assert value == "default"
    get_settings().remove(user_ui_settings_key(rel_key))


def test_bootstrap_migrates_pg_then_purges(pg_storage, monkeypatch: pytest.MonkeyPatch) -> None:
    from vnpy_ashare.storage.auth.preferences import get_pref, set_pref

    monkeypatch.setattr(
        "vnpy_ashare.config.preferences._local_ui_pref.get_user_id",
        lambda: "bootstrap-user",
    )
    monkeypatch.setattr("vnpy_ashare.storage.auth.scope.get_user_id", lambda: "bootstrap-user")

    set_pref("watchlist", "signal_panel", {"enabled": True, "symbols": "600519.SSE"})
    assert get_pref("watchlist", "signal_panel", None) is not None

    bootstrap_local_ui_prefs_from_pg()

    local = load_json_local_ui(
        "watchlist/signal_panel",
        load_default=lambda: {"enabled": False},
    )
    assert local == {"enabled": True, "symbols": "600519.SSE"}
    assert get_pref("watchlist", "signal_panel", None) is None
    assert purge_ui_prefs_from_pg() == 0

    get_settings().remove(user_ui_settings_key("watchlist/signal_panel"))
