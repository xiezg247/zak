"""内置选股方案定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SCREENER_CHANGE_TOP = "涨幅榜"
SCREENER_TURNOVER = "换手率排行"
SCREENER_VOLUME_SURGE = "成交量放大"
SCREENER_CUSTOM = "自定义筛选"
SCREENER_LOW_PE = "低 PE"
SCREENER_LARGE_CAP = "中大盘"
SCREENER_MONEYFLOW_IN = "主力净流入"

SourceKind = Literal["quote", "tushare"]


@dataclass(frozen=True)
class PresetDefinition:
    name: str
    source: SourceKind
    rule_kind: str
    description: str


BUILTIN_PRESETS: tuple[PresetDefinition, ...] = (
    PresetDefinition(SCREENER_CHANGE_TOP, "quote", "change_top", "Redis 行情 · 涨幅排序"),
    PresetDefinition(SCREENER_TURNOVER, "quote", "turnover", "Redis 行情 · 换手率排序"),
    PresetDefinition(SCREENER_VOLUME_SURGE, "quote", "volume", "Redis 行情 · 成交量排序"),
    PresetDefinition(SCREENER_CUSTOM, "quote", "custom", "Redis 行情 · 自定义区间"),
    PresetDefinition(SCREENER_LOW_PE, "tushare", "low_pe", "Tushare daily_basic · PE TTM < 15"),
    PresetDefinition(
        SCREENER_LARGE_CAP,
        "tushare",
        "large_cap",
        "Tushare daily_basic · 总市值 ≥ 50 亿",
    ),
    PresetDefinition(
        SCREENER_MONEYFLOW_IN,
        "tushare",
        "moneyflow_in",
        "Tushare moneyflow · 单日主力净流入 Top",
    ),
)

_PRESET_MAP = {item.name: item for item in BUILTIN_PRESETS}


def get_preset(name: str) -> PresetDefinition | None:
    return _PRESET_MAP.get(name.strip())


def list_builtin_preset_names() -> list[str]:
    return [item.name for item in BUILTIN_PRESETS]


def list_quote_preset_names() -> list[str]:
    return [item.name for item in BUILTIN_PRESETS if item.source == "quote"]


def list_tushare_preset_names() -> list[str]:
    return [item.name for item in BUILTIN_PRESETS if item.source == "tushare"]
