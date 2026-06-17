"""账户可交易市场板块（交易 Universe 上限）。

``ASHARE_TRADING_BOARDS`` 定义账户物理可交易范围；选股硬过滤 ``RECIPE_ALLOWED_MARKET_BOARDS``
仅能在该范围内进一步收窄，不能放大。
"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.config.constants.trading import ENV_TRADING_BOARDS
from vnpy_ashare.domain.core.env import env_str
from vnpy_ashare.domain.market.board import matches_board
from vnpy_ashare.screener.hard_filter_prefs import MARKET_BOARD_FILTER_OPTIONS, parse_allowed_market_boards

MARKET_BOARD_ALL_LABEL = "全部"


@dataclass(frozen=True, slots=True)
class MarketBoardFilter:
    """市场板块过滤解析结果。"""

    active: bool
    boards: frozenset[str]


def get_trading_allowed_boards() -> frozenset[str]:
    """账户可交易市场板块；空集表示不限制。"""
    return parse_allowed_market_boards(env_str(ENV_TRADING_BOARDS))


def effective_market_board_filter(*, recipe_boards: frozenset[str]) -> MarketBoardFilter:
    """合并账户交易上限与选股板块偏好。"""
    trading = get_trading_allowed_boards()
    if not trading and not recipe_boards:
        return MarketBoardFilter(active=False, boards=frozenset())
    if not trading:
        return MarketBoardFilter(active=True, boards=recipe_boards)
    if not recipe_boards:
        return MarketBoardFilter(active=True, boards=trading)
    return MarketBoardFilter(active=True, boards=trading & recipe_boards)


def effective_allowed_market_boards(*, recipe_boards: frozenset[str]) -> frozenset[str]:
    """有效板块集合（兼容旧调用）。"""
    return effective_market_board_filter(recipe_boards=recipe_boards).boards


def passes_trading_board(symbol: str) -> bool:
    """标的是否在账户可交易板块内；未配置交易上限时恒为 True。"""
    allowed = get_trading_allowed_boards()
    if not allowed:
        return True
    return any(matches_board(symbol, board) for board in allowed)


def trading_boards_hint() -> str:
    """供 UI 展示的交易范围说明；未限制时返回空串。"""
    allowed = get_trading_allowed_boards()
    if not allowed:
        return ""
    return "、".join(sorted(allowed))


def market_board_combo_labels() -> tuple[str, ...]:
    """市场页板块下拉可选项。"""
    allowed = get_trading_allowed_boards()
    if not allowed:
        return (MARKET_BOARD_ALL_LABEL, *MARKET_BOARD_FILTER_OPTIONS)
    permitted = tuple(board for board in MARKET_BOARD_FILTER_OPTIONS if board in allowed)
    if len(permitted) <= 1:
        return permitted
    return (MARKET_BOARD_ALL_LABEL, *permitted)


def default_market_board_label() -> str:
    """市场页默认选中项标签。"""
    allowed = get_trading_allowed_boards()
    if not allowed:
        return MARKET_BOARD_ALL_LABEL
    if "沪深主板" in allowed:
        return "沪深主板"
    return sorted(allowed)[0]


def market_board_label_to_filter(label: str) -> str | None:
    """下拉标签 → ``_market_board`` 过滤值；None 表示全部。"""
    text = str(label or "").strip()
    if not text or text == MARKET_BOARD_ALL_LABEL:
        return None
    return text


def is_market_board_combo_locked() -> bool:
    """仅单一可交易板块时锁定下拉（不可切换）。"""
    return len(get_trading_allowed_boards()) == 1
