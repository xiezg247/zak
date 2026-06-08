"""选股运行历史落库测试。"""

from __future__ import annotations

import sqlite3

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

    loaded = run_store.get_run(record.id)
    assert loaded is not None
    assert loaded.id == record.id

    latest = run_store.get_latest_run()
    assert latest is not None
    assert latest.id == record.id

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM screener_runs").fetchone()[0]
    assert count == 1
