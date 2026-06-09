"""选股运行历史落库测试。"""

from __future__ import annotations

from vnpy_ashare.screener import run_store


def test_save_and_list_runs(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(run_store, "APP_DB_PATH", db_path)

    record = run_store.save_run(
        condition="涨幅榜",
        source="redis",
        rows=[{"vt_symbol": "600000.SSE", "name": "浦发银行"}],
        total_scanned=100,
        config={"preset": "涨幅榜", "top_n": 20},
    )
    assert record.id
    assert record.row_count == 1
    assert record.total_scanned == 100

    runs = run_store.list_runs(limit=5)
    assert len(runs) == 1
    assert runs[0].condition == "涨幅榜"
    assert runs[0].rows[0]["name"] == "浦发银行"

    assert run_store.delete_run(record.id) is True
    assert run_store.list_runs(limit=5) == []


def test_mark_run_read(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(run_store, "APP_DB_PATH", db_path)

    record = run_store.save_run(
        condition="自动 · 盘中多因子",
        source="recipe",
        rows=[{"vt_symbol": "600000.SSE"}],
        config={"trigger": "scheduled_intraday", "recipe_id": "intraday_multi"},
    )
    assert run_store.is_auto_run(record.config) is True
    assert run_store.is_strategy_run({"trigger": "manual"}) is True
    assert run_store.is_auto_run({"trigger": "manual", "recipe_id": "abc"}) is True
    assert run_store.is_run_unread(record.config) is True

    assert run_store.mark_run_read(record.id) is True
    loaded = run_store.get_run(record.id)
    assert loaded is not None
    assert loaded.config.get("read_at")
    assert run_store.is_run_unread(loaded.config) is False
    assert run_store.mark_run_read(record.id) is True
