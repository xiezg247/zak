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
    patched: list[tuple] = []

    class _FakeConn:
        def execute(self, sql, params=()):
            sql_text = str(sql)
            if "SELECT symbol, exchange, name FROM watchlist" in sql_text:
                return _FakeRows(
                    [
                        {"symbol": "601138", "exchange": "SSE", "name": ""},
                        {"symbol": "600519", "exchange": "SSE", "name": "贵州茅台"},
                    ]
                )
            if "UPDATE watchlist SET name" in sql_text:
                patched.append(params)
            return _FakeRows([])

        def commit(self) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class _FakeRows:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    monkeypatch.setattr("vnpy_ashare.storage.repositories.watchlist_repair.connect", lambda: _FakeConn())
    monkeypatch.setattr("vnpy_ashare.storage.repositories.watchlist_repair.init_app_db", lambda: None)
    monkeypatch.setattr(
        "vnpy_ashare.storage.repositories.watchlist_repair.load_universe_names_for_keys",
        lambda keys: {("601138", Exchange.SSE): "工业富联"},
    )

    patches = repair_watchlist_names_for_user("uid-1", "alice", dry_run=False)
    assert len(patches) == 1
    assert patches[0].symbol == "601138"
    assert patches[0].new_name == "工业富联"
    assert patched == [("工业富联", "uid-1", "601138", "SSE")]


def test_name_map_for_symbols_uses_watchlist_only(monkeypatch) -> None:
    from vnpy_ashare.quotes.radar.radar_pool import name_map_for_symbols

    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.radar_pool.load_watchlist_rows",
        lambda: [("601138", Exchange.SSE, "工业富联")],
    )

    mapping = name_map_for_symbols(["601138.SSE", "600519.SSE"])
    assert mapping == {"601138.SSE": "工业富联"}
