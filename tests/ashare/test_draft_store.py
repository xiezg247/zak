"""draft_store 单元测试。"""

from __future__ import annotations

from vnpy_ashare.screener.draft_store import (
    cancel_draft,
    clear_drafts,
    consume_draft,
    get_draft,
    make_draft,
    save_draft,
)
from vnpy_ashare.screener.presets import SCREENER_CHANGE_TOP
from vnpy_ashare.screener.runner import ScreenerRequest


def _sample_draft(**kwargs):
    defaults = dict(
        natural_language="涨幅榜前10",
        request=ScreenerRequest(preset=SCREENER_CHANGE_TOP, top_n=10),
        summary="涨幅榜 · Top 10",
        preset_label=SCREENER_CHANGE_TOP,
        source="quote",
        confidence="high",
        warnings=[],
    )
    defaults.update(kwargs)
    return make_draft(**defaults)


def setup_function():
    clear_drafts()


def test_save_and_consume_once():
    draft = _sample_draft()
    save_draft(draft)
    loaded = get_draft(draft.id)
    assert loaded is not None
    assert loaded.status == "pending"

    consumed = consume_draft(draft.id)
    assert consumed is not None
    assert consumed.status == "confirmed"
    assert consume_draft(draft.id) is None


def test_cancel_draft():
    draft = _sample_draft()
    save_draft(draft)
    assert cancel_draft(draft.id) is True
    loaded = get_draft(draft.id)
    assert loaded is not None
    assert loaded.status == "cancelled"
    assert consume_draft(draft.id) is None


def test_expired_draft():
    draft = _sample_draft(ttl_minutes=-1)
    save_draft(draft)
    loaded = get_draft(draft.id)
    assert loaded is not None
    assert loaded.status == "expired"
    assert consume_draft(draft.id) is None
