"""自选池证券名称修复测试。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.storage.repositories.watchlist_repair import (
    _resolve_name,
    repair_watchlist_names_for_user,
)


def test_resolve_name_prefers_legacy() -> None:
    resolved = _resolve_name(
        "601138",
        Exchange.SSE,
        legacy_names={("601138", "SSE"): "工业富联"},
        universe_names={("601138", Exchange.SSE): "错误名称"},
    )
    assert resolved == ("工业富联", "legacy")


def test_resolve_name_falls_back_to_universe() -> None:
    resolved = _resolve_name(
        "600497",
        Exchange.SSE,
        legacy_names={},
        universe_names={("600497", Exchange.SSE): "驰宏锌锗"},
    )
    assert resolved == ("驰宏锌锗", "universe")


def test_repair_watchlist_names_for_user_only_fills_empty(monkeypatch) -> None:
    from vnpy_ashare.storage.repositories.watchlist import WatchlistRepository

    updates: list[int] = []

    def mock_fetchall(self, _stmt):
        return [
            {"symbol": "601138", "exchange": "SSE", "name": ""},
            {"symbol": "600519", "exchange": "SSE", "name": "贵州茅台"},
        ]

    def mock_run(self, callback):
        class _Conn:
            def execute_stmt(self, _stmt):
                updates.append(1)

        callback(_Conn())

    monkeypatch.setattr(WatchlistRepository, "fetchall", mock_fetchall)
    monkeypatch.setattr(WatchlistRepository, "run", mock_run)
    monkeypatch.setattr(
        "vnpy_ashare.storage.repositories.watchlist_repair.load_universe_names_for_keys",
        lambda keys: {("601138", Exchange.SSE): "工业富联"},
    )

    patches = repair_watchlist_names_for_user("uid-1", "alice", dry_run=False)
    assert len(patches) == 1
    assert patches[0].symbol == "601138"
    assert patches[0].new_name == "工业富联"
    assert len(updates) == 1


def test_name_map_for_symbols_uses_watchlist_only(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_pool import name_map_for_symbols

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_pool.load_watchlist_rows",
        lambda: [("601138", Exchange.SSE, "工业富联")],
    )

    mapping = name_map_for_symbols(["601138.SSE", "600519.SSE"])
    assert mapping == {"601138.SSE": "工业富联"}
