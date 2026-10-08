"""雷达页批量加入自选（纯逻辑，无 Qt notify）。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols.stock import parse_stock_symbol


class _WatchlistAdder(Protocol):
    def add(self, symbol: str, exchange: Exchange, name: str = "") -> bool: ...

    def add_failure_reason(self, symbol: str, exchange: Exchange) -> Literal["duplicate", "full"] | None: ...


@dataclass(frozen=True)
class WatchlistBatchResult:
    added: int
    skipped: int
    full_hit: bool


@dataclass(frozen=True)
class WatchlistNotify:
    message: str
    level: str = "info"  # info | warning


def add_vt_symbols_to_watchlist(
    service: _WatchlistAdder,
    pairs: Iterable[tuple[str, str]],
) -> WatchlistBatchResult:
    """按 (vt_symbol, display_name) 批量加入；遇满员提前停止。"""
    added = skipped = 0
    full_hit = False
    for vt_symbol, display_name in pairs:
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            skipped += 1
            continue
        name = str(display_name or item.name or "").strip()
        if service.add(item.symbol, item.exchange, name):
            added += 1
            continue
        reason = service.add_failure_reason(item.symbol, item.exchange)
        if reason == "full":
            full_hit = True
            break
        skipped += 1
    return WatchlistBatchResult(added=added, skipped=skipped, full_hit=full_hit)


def format_watchlist_batch_notify(
    result: WatchlistBatchResult,
    *,
    full_prefix: str = "自选池已满，已加入",
    all_skipped_message: str = "全部已在自选池中",
    success_prefix: str = "已加入",
) -> WatchlistNotify:
    if result.full_hit:
        return WatchlistNotify(f"{full_prefix} {result.added} 只", level="warning")
    if result.added == 0 and result.skipped:
        return WatchlistNotify(f"{all_skipped_message}（{result.skipped} 只）")
    message = f"{success_prefix} {result.added} 只"
    if result.skipped:
        message += f"，跳过 {result.skipped} 只"
    return WatchlistNotify(message)


def format_single_watchlist_add(
    *,
    ok: bool,
    display_name: str,
    vt_symbol: str,
    reason: Literal["duplicate", "full"] | None = None,
) -> WatchlistNotify:
    """单标的加入自选结果文案。"""
    if ok:
        return WatchlistNotify(f"已加入自选：{display_name or vt_symbol}")
    if reason == "full":
        return WatchlistNotify("自选池已满", level="warning")
    return WatchlistNotify(f"已在自选池中：{vt_symbol}")


def format_watchlist_pool_notify(*, watchlist_added: int, skipped: int) -> WatchlistNotify:
    """龙一入自选等「仅写池」结果文案。"""
    if watchlist_added == 0:
        if skipped:
            return WatchlistNotify("标的已在自选池或无法加入")
        return WatchlistNotify("暂无可加入自选的标的", level="warning")
    parts = [f"已加入自选 {watchlist_added} 只"]
    if skipped:
        parts.append(f"跳过 {skipped} 只")
    return WatchlistNotify(" · ".join(parts))


def format_short_term_focus_notify(
    *,
    group_name: str,
    group_added: int,
    watchlist_added: int,
    skipped: int,
) -> WatchlistNotify:
    """写入短线关注分组结果文案。"""
    parts = [f"已写入「{group_name}」{group_added} 只"]
    if watchlist_added:
        parts.append(f"新增自选 {watchlist_added} 只")
    if skipped:
        parts.append(f"跳过 {skipped} 只")
    return WatchlistNotify(" · ".join(parts))
