"""选股 Service。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy_ashare.services.base import BaseService

SCREENER_CHANGE_TOP = "涨幅榜"
SCREENER_TURNOVER = "换手率排行"
SCREENER_VOLUME_SURGE = "成交量放大"

AVAILABLE_SCREENERS = [SCREENER_CHANGE_TOP, SCREENER_TURNOVER, SCREENER_VOLUME_SURGE]


@dataclass
class Candidate:
    symbol: str
    name: str
    vt_symbol: str
    last_price: float
    change_pct: float
    turnover_rate: float
    volume: float


class ScreeningService(BaseService):
    """执行选股条件，返回候选标的。"""

    def list_screeners(self) -> list[str]:
        return list(AVAILABLE_SCREENERS)

    def screen_by_condition(
        self,
        name: str,
        quotes: list[dict[str, Any]],
        *,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        name = name.strip()
        if name == SCREENER_CHANGE_TOP:
            sorted_quotes = sorted(
                quotes, key=lambda q: q.get("change_pct", 0), reverse=True
            )
        elif name == SCREENER_TURNOVER:
            sorted_quotes = sorted(
                quotes, key=lambda q: q.get("turnover_rate", 0), reverse=True
            )
        elif name == SCREENER_VOLUME_SURGE:
            sorted_quotes = sorted(
                quotes, key=lambda q: q.get("volume", 0), reverse=True
            )
        else:
            return []
        return sorted_quotes[:top_n]

    def screen_custom(
        self,
        quotes: list[dict[str, Any]],
        *,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        min_turnover: float | None = None,
        top_n: int = 20,
    ) -> list[dict[str, Any]]:
        result = quotes
        if min_change_pct is not None:
            result = [q for q in result if q.get("change_pct", 0) >= min_change_pct]
        if max_change_pct is not None:
            result = [q for q in result if q.get("change_pct", 0) <= max_change_pct]
        if min_turnover is not None:
            result = [q for q in result if q.get("turnover_rate", 0) >= min_turnover]
        result = sorted(result, key=lambda q: q.get("change_pct", 0), reverse=True)
        return result[:top_n]
