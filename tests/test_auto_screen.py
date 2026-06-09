"""自动选股轨解析单元测试。"""

from __future__ import annotations

from vnpy_ashare.screener.auto_screen import AutoScreenInput, resolve_auto_screen_request


def test_builtin_preset_ok():
    result = resolve_auto_screen_request(
        AutoScreenInput(name="涨幅榜", top_n=10)
    )
    assert result.ok is True
    assert result.request is not None
    assert result.request.preset == "涨幅榜"
    assert result.request.top_n == 10


def test_saved_scheme_need_confirm():
    result = resolve_auto_screen_request(
        AutoScreenInput(name="我的 · 测试方案")
    )
    assert result.ok is False
    assert result.need_confirm is True


def test_custom_with_threshold_ok():
    result = resolve_auto_screen_request(
        AutoScreenInput(
            name="自定义筛选",
            top_n=20,
            min_change_pct=3.0,
            min_turnover=1.0,
        )
    )
    assert result.ok is True
    assert result.request is not None
    assert result.request.min_change_pct == 3.0


def test_unknown_preset_error():
    result = resolve_auto_screen_request(
        AutoScreenInput(name="不存在方案")
    )
    assert result.ok is False
    assert result.error
