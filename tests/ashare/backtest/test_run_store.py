"""回测运行历史落库测试。"""

from __future__ import annotations

import sqlite3
from datetime import date

import vnpy_ashare.backtest.run_store as run_store


def test_save_and_list_backtest_runs(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(run_store, "get_app_db_path", lambda settings=None: db_path)

    record = run_store.save_backtest_run(
        vt_symbol="600000.SSE",
        strategy="DoubleMaStrategy",
        interval="d",
        start="2020-01-01",
        end="2024-12-31",
        statistics={
            "total_return": "12.5",
            "max_drawdown": "-8.2",
            "sharpe_ratio": "1.1",
            "total_trade_count": 42,
        },
        source="single",
    )
    assert record.total_return == 12.5
    assert record.trade_count == 42

    runs = run_store.list_backtest_runs(limit=5)
    assert len(runs) == 1
    assert runs[0].vt_symbol == "600000.SSE"

    summary = runs[0].to_summary_dict()
    assert summary["strategy"] == "DoubleMaStrategy"
    assert summary["statistics"]["total_trade_count"] == 42

    latest = run_store.get_latest_backtest_run()
    assert latest is not None
    assert latest.id == record.id

    run_store.save_backtest_run(
        vt_symbol="000001.SZSE",
        strategy="DoubleMaStrategy",
        interval="d",
        start="2020-01-01",
        end="2024-12-31",
        source="batch_screener",
        batch_id="batch-test-1",
        statistics={"name": "平安银行"},
        total_return=8.0,
    )
    sessions = run_store.list_batch_sessions(limit=5)
    assert len(sessions) == 1
    assert sessions[0].batch_id == "batch-test-1"
    batch_rows = run_store.list_runs_by_batch("batch-test-1")
    assert len(batch_rows) == 1

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0]
    assert count == 2


def test_save_statistics_with_date(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(run_store, "get_app_db_path", lambda settings=None: db_path)

    record = run_store.save_backtest_run(
        vt_symbol="600000.SSE",
        strategy="DoubleMaStrategy",
        interval="d",
        start="2020-01-01",
        end="2024-12-31",
        statistics={"start_trade_date": date(2020, 1, 1)},
    )
    loaded = run_store.get_backtest_run(record.id)
    assert loaded is not None
    assert loaded.raw_statistics["start_trade_date"] == "2020-01-01"
