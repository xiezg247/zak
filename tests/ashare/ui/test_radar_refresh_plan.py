"""雷达盘中刷新与权重重载计划。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.loaders import RadarCardData, RadarRow
from vnpy_ashare.ui.quotes.radar.refresh_plan import (
    live_quote_refresh_candidates,
    reload_ids_after_resonance_weight_change,
    should_run_card_auto_refresh,
)
from vnpy_ashare.ui.quotes.radar.watchlist_batch import (
    format_short_term_focus_notify,
    format_watchlist_pool_notify,
)


def _row(vt: str) -> RadarRow:
    return RadarRow(
        vt_symbol=vt,
        name="测",
        symbol=vt.split(".")[0],
        price=1.0,
        change_pct=0.0,
        metric_label="",
        metric_value="",
        sub_label="",
        sub_value="",
    )


def _card(card_id: str, *rows: RadarRow) -> RadarCardData:
    return RadarCardData(
        card_id=card_id,
        title=card_id,
        subtitle="",
        rows=rows,
        empty_message="" if rows else "空",
        updated_at="",
    )


def test_live_quote_refresh_candidates() -> None:
    payload = {
        "a": _card("a", _row("600000.SSE")),
        "b": _card("b"),
        "c": _card("c", _row("__stat__:emotion")),
    }
    pending = live_quote_refresh_candidates(payload, ["a", "b", "c", "missing"])
    assert [cid for cid, _ in pending] == ["a"]


def test_should_run_card_auto_refresh() -> None:
    assert should_run_card_auto_refresh(visible=True, interval_ms=3000, in_session=True)
    assert not should_run_card_auto_refresh(visible=False, interval_ms=3000, in_session=True)
    assert not should_run_card_auto_refresh(visible=True, interval_ms=0, in_session=True)
    assert not should_run_card_auto_refresh(visible=True, interval_ms=3000, in_session=False)


def test_reload_ids_after_resonance_weight_change() -> None:
    ids = reload_ids_after_resonance_weight_change(
        ["leader_pick", "outlook_predict", "sector_theme", "other"],
        weight_card_ids=["leader_pick", "outlook_predict", "sector_theme"],
    )
    assert ids == ["leader_pick", "sector_theme"]


def test_watchlist_notify_helpers() -> None:
    empty = format_watchlist_pool_notify(watchlist_added=0, skipped=0)
    assert empty.level == "warning"
    skipped = format_watchlist_pool_notify(watchlist_added=0, skipped=2)
    assert "已在自选" in skipped.message
    ok = format_watchlist_pool_notify(watchlist_added=3, skipped=1)
    assert "3" in ok.message and "跳过" in ok.message

    focus = format_short_term_focus_notify(
        group_name="短线关注",
        group_added=2,
        watchlist_added=1,
        skipped=0,
    )
    assert "短线关注" in focus.message and "新增自选" in focus.message
