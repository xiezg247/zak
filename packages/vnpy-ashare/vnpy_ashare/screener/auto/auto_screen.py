"""自动选股轨：Skill 直跑 preset 的资格判断与 Request 解析。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel, MutableModel
from vnpy_ashare.screener.draft.nl_mapper import clamp_top_n, normalize_preset_name
from vnpy_ashare.screener.preset.presets import SCREENER_CUSTOM, get_preset
from vnpy_ashare.screener.run.runner import ScreenerRequest, resolve_preset_input


class AutoScreenInput(FrozenModel):
    """Skill screen_by_condition 的结构化输入。"""

    name: str = Field(description="选股条件名称")
    top_n: int = Field(default=20, description="返回条数上限")
    min_change_pct: float | None = Field(default=None, description="最低涨幅（%）")
    max_change_pct: float | None = Field(default=None, description="最高涨幅（%）")
    min_turnover: float | None = Field(default=None, description="最低换手率（%）")


class AutoScreenResult(MutableModel):
    """解析结果：可直接执行 / 错误。"""

    ok: bool = Field(description="是否解析成功")
    request: ScreenerRequest | None = Field(default=None, description="解析后的选股请求")
    error: str = Field(default="", description="错误信息")


def resolve_auto_screen_request(data: AutoScreenInput) -> AutoScreenResult:
    """将 preset 名解析为 ScreenerRequest；不可直跑时返回 error。"""
    name = (data.name or "").strip()
    if not name:
        return AutoScreenResult(ok=False, error="name 不能为空")

    top_n = clamp_top_n(data.top_n)

    if name.startswith("我的 · "):
        try:
            request = resolve_preset_input(name)
        except ValueError as ex:
            return AutoScreenResult(ok=False, error=str(ex))
        return AutoScreenResult(
            ok=True,
            request=ScreenerRequest(
                preset=request.preset,
                top_n=top_n,
                scheme_id=request.scheme_id,
            ),
        )

    preset_name = normalize_preset_name(name)
    if not preset_name:
        return AutoScreenResult(ok=False, error=f"未知选股条件「{name}」")

    preset = get_preset(preset_name)
    if preset is None:
        return AutoScreenResult(ok=False, error=f"未知选股条件「{preset_name}」")

    if preset.name == SCREENER_CUSTOM:
        if data.min_change_pct is None and data.max_change_pct is None and data.min_turnover is None:
            return AutoScreenResult(
                ok=False,
                error="自定义筛选须指定 min_change_pct、max_change_pct 或 min_turnover 之一。",
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
