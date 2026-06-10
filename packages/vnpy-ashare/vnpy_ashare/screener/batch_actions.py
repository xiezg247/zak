"""选股结果批量操作（下载 K 线、批量回测）。"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.backtest.batch_runner import (
    batch_backtest_max_workers,
    run_single_backtest_task,
    task_from_params,
)
from vnpy_ashare.backtest.run_store import save_backtest_run
from vnpy_ashare.config import ASHARE_BACKTEST_DEFAULTS, BACKTESTER_SETTING_FILE
from vnpy_ashare.data.bars import download_bars
from vnpy_ashare.data.download_concurrency import download_max_workers, run_parallel_map
from vnpy_ashare.domain.models import StockItem
from vnpy_ashare.jobs.result import JobResult


@dataclass(frozen=True)
class BatchBacktestParams:
    """批量回测共用参数（策略、区间、费率）。"""

    class_name: str
    start: datetime
    end: datetime
    interval: Interval = Interval.DAILY
    rate: float = ASHARE_BACKTEST_DEFAULTS["rate"]
    slippage: float = ASHARE_BACKTEST_DEFAULTS["slippage"]
    size: int = ASHARE_BACKTEST_DEFAULTS["size"]
    pricetick: float = ASHARE_BACKTEST_DEFAULTS["pricetick"]
    capital: float = ASHARE_BACKTEST_DEFAULTS["capital"]
    strategy_setting: Mapping[str, Any] | None = None


@dataclass
class BatchBacktestRow:
    """单标的批量回测结果行。"""

    vt_symbol: str
    name: str
    total_return: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    total_trade_count: int | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "vt_symbol": self.vt_symbol,
            "name": self.name,
            "total_return": self.total_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "total_trade_count": self.total_trade_count,
            "error": self.error,
        }


def rows_to_stock_items(rows: list[dict[str, Any]]) -> list[StockItem]:
    """选股结果行 → 去重 StockItem 列表。"""
    items: list[StockItem] = []
    seen: set[tuple[str, Exchange]] = set()
    for row in rows:
        vt_symbol = str(row.get("vt_symbol", ""))
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        key = (item.symbol, item.exchange)
        if key in seen:
            continue
        seen.add(key)
        name = str(row.get("name", "") or item.name)
        items.append(StockItem(symbol=item.symbol, exchange=item.exchange, name=name))
    return items


def batch_download_daily_bars(
    rows: list[dict[str, Any]],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    delay: float = 0.3,
    max_workers: int | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> JobResult:
    """对选股结果批量下载日 K（默认 2020-01-01 至今）。"""
    items = rows_to_stock_items(rows)
    if not items:
        return JobResult(success=False, message="没有可下载的有效标的")

    start_dt = start or datetime(2020, 1, 1)
    end_dt = end or datetime.now()
    workers = max_workers if max_workers is not None else download_max_workers(item_count=len(items))

    def _download_one(item: StockItem) -> tuple[str, bool]:
        try:
            download_bars(
                symbol=item.symbol,
                exchange=item.exchange,
                interval=Interval.DAILY,
                start=start_dt,
                end=end_dt,
                output=lambda _msg: None,
            )
            return item.vt_symbol, True
        except Exception:
            return item.vt_symbol, False

    if workers <= 1:
        success = 0
        failed: list[str] = []
        for index, item in enumerate(items, start=1):
            if should_cancel is not None and should_cancel():
                return JobResult(success=False, message="日 K 下载已取消")
            _, ok = _download_one(item)
            if ok:
                success += 1
            else:
                failed.append(item.vt_symbol)
            if index < len(items) and delay > 0:
                time.sleep(delay)
    else:
        results = run_parallel_map(items, _download_one, max_workers=workers)
        success = sum(1 for _, ok in results if ok)
        failed = [symbol for symbol, ok in results if not ok]

    if failed:
        return JobResult(
            success=False,
            message=f"日 K 下载：成功 {success}，失败 {len(failed)}（{', '.join(failed[:5])}）",
        )
    return JobResult(success=True, message=f"已下载 {success} 只日 K")


def load_batch_backtest_defaults() -> BatchBacktestParams:
    """从 ASHARE_BACKTEST_DEFAULTS 与 vt_setting 合并读取默认回测参数。"""
    data: dict[str, Any] = dict(ASHARE_BACKTEST_DEFAULTS)
    if BACKTESTER_SETTING_FILE.is_file():
        try:
            loaded = json.loads(BACKTESTER_SETTING_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

    start_text = str(data.get("start", "2020-01-01"))
    end_text = str(data.get("end", datetime.now().strftime("%Y-%m-%d")))
    return BatchBacktestParams(
        class_name=str(data.get("class_name", ASHARE_BACKTEST_DEFAULTS["class_name"])),
        start=datetime.strptime(start_text[:10], "%Y-%m-%d"),
        end=datetime.strptime(end_text[:10], "%Y-%m-%d"),
        rate=float(data.get("rate", ASHARE_BACKTEST_DEFAULTS["rate"])),
        slippage=float(data.get("slippage", ASHARE_BACKTEST_DEFAULTS["slippage"])),
        size=int(data.get("size", ASHARE_BACKTEST_DEFAULTS["size"])),
        pricetick=float(data.get("pricetick", ASHARE_BACKTEST_DEFAULTS["pricetick"])),
        capital=float(data.get("capital", ASHARE_BACKTEST_DEFAULTS["capital"])),
    )


def run_batch_backtests(
    main_engine,
    rows: list[dict[str, Any]],
    params: BatchBacktestParams,
) -> list[BatchBacktestRow]:
    """批量回测：多标的时进程池并行，单标的走 MainEngine 回测引擎。"""
    from vnpy_ctabacktester.engine import APP_NAME, BacktesterEngine

    engine = main_engine.get_engine(APP_NAME)
    if not isinstance(engine, BacktesterEngine):
        raise RuntimeError("回测引擎未加载")

    items = rows_to_stock_items(rows)
    if not items:
        return []

    setting: dict[str, Any] = dict(params.strategy_setting or {})
    workers = batch_backtest_max_workers(item_count=len(items))
    if workers > 1:
        tasks = [task_from_params(item, params, class_name=params.class_name, setting=setting) for item in items]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            payloads = list(pool.map(run_single_backtest_task, tasks, chunksize=1))
        return [_batch_row_from_payload(payload) for payload in payloads]

    results: list[BatchBacktestRow] = []
    for item in items:
        row = BatchBacktestRow(vt_symbol=item.vt_symbol, name=item.name)
        try:
            engine.run_backtesting(
                params.class_name,
                item.vt_symbol,
                params.interval,
                params.start,
                params.end,
                params.rate,
                params.slippage,
                params.size,
                params.pricetick,
                params.capital,
                setting,
            )
            stats = engine.get_result_statistics() or {}
            row.total_return = _to_float(stats.get("total_return"))
            row.max_drawdown = _to_float(stats.get("max_drawdown"))
            row.sharpe_ratio = _to_float(stats.get("sharpe_ratio"))
            trade_count = stats.get("total_trade_count")
            row.total_trade_count = int(trade_count) if trade_count is not None else None
        except Exception as ex:
            row.error = str(ex)
        results.append(row)
    return results


def _batch_row_from_payload(payload: dict[str, Any]) -> BatchBacktestRow:
    return BatchBacktestRow(
        vt_symbol=str(payload.get("vt_symbol", "")),
        name=str(payload.get("name", "")),
        total_return=payload.get("total_return"),
        max_drawdown=payload.get("max_drawdown"),
        sharpe_ratio=payload.get("sharpe_ratio"),
        total_trade_count=payload.get("total_trade_count"),
        error=str(payload.get("error") or ""),
    )


def persist_batch_backtest_results(
    params: BatchBacktestParams,
    rows: list[BatchBacktestRow],
    *,
    source: str = "batch_screener",
) -> str:
    """批量回测结果落库，返回 batch_id。"""
    batch_id = uuid.uuid4().hex
    interval = params.interval.value if hasattr(params.interval, "value") else str(params.interval)
    start_text = params.start.strftime("%Y-%m-%d")
    end_text = params.end.strftime("%Y-%m-%d")
    for row in rows:
        stats: dict[str, Any] = {"name": row.name}
        if row.error:
            stats["error"] = row.error
        save_backtest_run(
            vt_symbol=row.vt_symbol,
            strategy=params.class_name,
            interval=interval,
            start=start_text,
            end=end_text,
            source=source,
            batch_id=batch_id,
            statistics=stats,
            total_return=row.total_return if not row.error else None,
            max_drawdown=row.max_drawdown if not row.error else None,
            sharpe_ratio=row.sharpe_ratio if not row.error else None,
            trade_count=row.total_trade_count if not row.error else None,
        )
    return batch_id


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        text = str(value).replace("%", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return None


def watchlist_items_to_rows(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """WatchlistService.get_items() → 批量回测行。"""
    rows: list[dict[str, str]] = []
    for item in items:
        symbol = str(item.get("symbol", "")).strip()
        exchange = str(item.get("exchange", "")).strip()
        if not symbol or not exchange:
            continue
        rows.append(
            {
                "vt_symbol": f"{symbol}.{exchange}",
                "name": str(item.get("name", "") or ""),
            }
        )
    return rows


def stock_items_to_batch_rows(stocks: list[StockItem]) -> list[dict[str, str]]:
    """StockItem 列表 → 批量回测输入行。"""
    return [{"vt_symbol": item.vt_symbol, "name": item.name} for item in stocks]
