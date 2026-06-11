"""自动选股轨：Skill 直跑 preset 的资格判断与 Request 解析。

与 ``nl_mapper`` 不同：已保存方案 / 无阈值的自定义筛选须走 ``propose_screening`` 确认。
"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.screener.draft.nl_mapper import clamp_top_n, normalize_preset_name
from vnpy_ashare.screener.preset.presets import SCREENER_CUSTOM, get_preset
from vnpy_ashare.screener.run.runner import ScreenerRequest


@dataclass(frozen=True)
class AutoScreenInput:
    """Skill screen_by_condition 的结构化输入。"""

    name: str
    top_n: int = 20
    min_change_pct: float | None = None
    max_change_pct: float | None = None
    min_turnover: float | None = None


@dataclass
class AutoScreenResult:
    """解析结果：可直接执行 / 需确认 / 错误。"""

    ok: bool
    request: ScreenerRequest | None = None
    need_confirm: bool = False
    error: str = ""


def resolve_auto_screen_request(data: AutoScreenInput) -> AutoScreenResult:
    """将 preset 名解析为 ScreenerRequest；不可直跑时设 need_confirm 或 error。"""
    name = (data.name or "").strip()
    if not name:
        return AutoScreenResult(ok=False, error="name 不能为空")

    if name.startswith("我的 · "):
        return AutoScreenResult(
            ok=False,
            need_confirm=True,
            error="已保存方案须通过 propose_screening 确认后执行。",
        )

    preset_name = normalize_preset_name(name)
    if not preset_name:
        return AutoScreenResult(ok=False, error=f"未知选股条件「{name}」")

    preset = get_preset(preset_name)
    if preset is None:
        return AutoScreenResult(ok=False, error=f"未知选股条件「{preset_name}」")

    top_n = clamp_top_n(data.top_n)
    if preset.name == SCREENER_CUSTOM:
        if data.min_change_pct is None and data.max_change_pct is None and data.min_turnover is None:
            return AutoScreenResult(
                ok=False,
                need_confirm=True,
                error="自定义筛选须指定涨幅或换手率阈值，或改用 propose_screening。",
            )
        request = ScreenerRequest(
            preset=preset.name,
            top_n=top_n,
            min_change_pct=data.min_change_pct,
            max_change_pct=data.max_change_pct,
            min_turnover=data.min_turnover,
        )
    else:
        request = ScreenerRequest(preset=preset.name, top_n=top_n)

    return AutoScreenResult(ok=True, request=request)
