"""内置选股方案定义。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_common.domain.base import FrozenModel

SCREENER_CHANGE_TOP = "涨幅榜"
SCREENER_TURNOVER = "换手率排行"
SCREENER_VOLUME_SURGE = "成交量放大"
SCREENER_STRONG_UP = "强势上涨"
SCREENER_VOLUME_RATIO = "量比排行"
SCREENER_CUSTOM = "自定义筛选"
SCREENER_LOW_PE = "低 PE"
SCREENER_LARGE_CAP = "中大盘"
SCREENER_MONEYFLOW_IN = "主力净流入"
SCREENER_LIMIT_UP = "涨停股"

SCHEME_KIND_INDUSTRY = "industry"

SourceKind = Literal["quote", "tushare"]


class PresetDefinition(FrozenModel):
    """内置选股方案元数据。

    ``source``：quote（Redis 行情）或 tushare；
    ``rule_kind``：rules 模块内的规则分支标识。
    """

    name: str = Field(description="方案显示名")
    source: SourceKind = Field(description="数据来源类型")
    rule_kind: str = Field(description="规则分支标识")
    description: str = Field(description="方案说明")


BUILTIN_PRESETS: tuple[PresetDefinition, ...] = (
    PresetDefinition(name=SCREENER_CHANGE_TOP, source="quote", rule_kind="change_top", description="Redis 行情 · 涨幅排序"),
    PresetDefinition(name=SCREENER_STRONG_UP, source="quote", rule_kind="strong_up", description="Redis 行情 · 涨幅 ≥ 5%"),
    PresetDefinition(name=SCREENER_TURNOVER, source="quote", rule_kind="turnover", description="Redis 行情 · 换手率排序"),
    PresetDefinition(name=SCREENER_VOLUME_RATIO, source="quote", rule_kind="volume_ratio", description="Redis+Tushare · 量比排序"),
    PresetDefinition(name=SCREENER_VOLUME_SURGE, source="quote", rule_kind="volume", description="Redis 行情 · 成交量排序"),
    PresetDefinition(name=SCREENER_CUSTOM, source="quote", rule_kind="custom", description="Redis 行情 · 自定义区间"),
    PresetDefinition(name=SCREENER_LOW_PE, source="tushare", rule_kind="low_pe", description="Tushare daily_basic · PE TTM < 15"),
    PresetDefinition(name=SCREENER_LARGE_CAP, source="tushare", rule_kind="large_cap", description="Tushare daily_basic · 总市值 ≥ 50 亿"),
    PresetDefinition(name=SCREENER_MONEYFLOW_IN, source="tushare", rule_kind="moneyflow_in", description="Tushare moneyflow · 单日主力净流入 Top"),
    PresetDefinition(name=SCREENER_LIMIT_UP, source="tushare", rule_kind="limit_up", description="Tushare limit_list_d · 当日涨停"),
)

_PRESET_MAP = {item.name: item for item in BUILTIN_PRESETS}


def get_preset(name: str) -> PresetDefinition | None:
    """按显示名查找内置 preset。"""
    return _PRESET_MAP.get(name.strip())


def list_builtin_preset_names() -> list[str]:
    """全部内置 preset 显示名。"""
    return [item.name for item in BUILTIN_PRESETS]


def list_quote_preset_names() -> list[str]:
    """Redis 行情类 preset 名称。"""
    return [item.name for item in BUILTIN_PRESETS if item.source == "quote"]


def list_tushare_preset_names() -> list[str]:
    """Tushare 基本面类 preset 名称。"""
    return [item.name for item in BUILTIN_PRESETS if item.source == "tushare"]
