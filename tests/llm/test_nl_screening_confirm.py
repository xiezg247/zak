"""NL 选股确认文案与偏好测试。"""

from __future__ import annotations

from vnpy_llm.config.nl_screening_prefs import (
    load_nl_screening_confirm_enabled,
    save_nl_screening_confirm_enabled,
)
from vnpy_llm.ui.nl_screening_confirm import (
    build_nl_screening_confirm_summary,
    confirm_nl_screening_tool,
)


def test_build_nl_screening_confirm_summary_screening() -> None:
    text = build_nl_screening_confirm_summary(
        "propose_screening",
        {"scheme_name": "我的 · 低PE", "top_n": 15, "intent": "低估值"},
    )
    assert "条件选股" in text
    assert "我的 · 低PE" in text
    assert "15" in text


def test_build_nl_screening_confirm_summary_recipe() -> None:
    text = build_nl_screening_confirm_summary(
        "propose_recipe",
        {"intent": "盘中强势股", "recipe_id": "intraday_multi", "top_n": 20},
    )
    assert "多因子" in text
    assert "盘中强势股" in text
    assert "intraday_multi" in text


def test_confirm_skipped_when_disabled() -> None:
    save_nl_screening_confirm_enabled(False)
    try:
        assert confirm_nl_screening_tool("propose_screening", {"intent": "test"}) is True
    finally:
        save_nl_screening_confirm_enabled(True)


def test_confirm_enabled_by_default() -> None:
    assert load_nl_screening_confirm_enabled() is True
