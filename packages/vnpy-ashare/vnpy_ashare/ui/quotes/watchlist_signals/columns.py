"""策略信号区表格列定义与可见性。"""

from __future__ import annotations

SIGNAL_PANEL_FIXED_KEYS: frozenset[str] = frozenset({"symbol", "name"})

SIGNAL_PANEL_OPTIONAL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("signal", "信号"),
    ("signal_age", "信号天"),
    ("volume_ratio", "量比"),
    ("ma_gap_pct", "快慢距%"),
    ("anchor_buy", "支撑锚点"),
    ("anchor_sell", "阻力锚点"),
    ("ref_buy_price", "参考买价"),
    ("ref_sell_price", "参考卖价"),
    ("dist_buy_pct", "距买价%"),
    ("dist_sell_pct", "距卖价%"),
    ("signal_strength", "强度"),
    ("relative_index_pct", "相对300%"),
    ("has_position", "持仓"),
    ("position_pnl_pct", "浮盈%"),
)

SIGNAL_PANEL_OPTIONAL_KEYS: frozenset[str] = frozenset(key for key, _ in SIGNAL_PANEL_OPTIONAL_COLUMNS)

DEFAULT_VISIBLE_OPTIONAL_KEYS: tuple[str, ...] = tuple(key for key, _ in SIGNAL_PANEL_OPTIONAL_COLUMNS)

SIGNAL_PANEL_RUNTIME_KEYS: frozenset[str] = frozenset({"has_position", "position_pnl_pct"})


def normalize_visible_optional_keys(keys: list[str] | None) -> list[str]:
    """去重、过滤非法键；空结果回退默认列。"""
    if not keys:
        return list(DEFAULT_VISIBLE_OPTIONAL_KEYS)
    order = {key: index for index, key in enumerate(DEFAULT_VISIBLE_OPTIONAL_KEYS)}
    cleaned: list[str] = []
    seen: set[str] = set()
    for key in keys:
        text = str(key or "").strip()
        if text not in SIGNAL_PANEL_OPTIONAL_KEYS or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    if not cleaned:
        return list(DEFAULT_VISIBLE_OPTIONAL_KEYS)
    cleaned.sort(key=lambda item: order.get(item, len(order)))
    return cleaned


def resolve_signal_panel_columns(visible_optional_keys: list[str]) -> tuple[tuple[str, str], ...]:
    """固定列 + 用户可见可选列。"""
    visible = set(normalize_visible_optional_keys(visible_optional_keys))
    optional = [item for item in SIGNAL_PANEL_OPTIONAL_COLUMNS if item[0] in visible]
    return (("symbol", "代码"), ("name", "名称"), *optional)
