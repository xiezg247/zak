"""选股结果批量操作（下载 K 线、批量回测）。"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy.trader.constant import Exchange, Interval

from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.bars import download_bars
from vnpy_ashare.config import ASHARE_BACKTEST_DEFAULTS, BACKTESTER_SETTING_FILE
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.models import StockItem


@dataclass(frozen=True)
class BatchBacktestParams:
    class_name: str
    start: datetime
    end: datetime
    interval: Interval = Interval.DAILY
    rate: float = ASHARE_BACKTEST_DEFAULTS["rate"]
    slippage: float = ASHARE_BACKTEST_DEFAULTS["slippage"]
    size: int = ASHARE_BACKTEST_DEFAULTS["size"]
    pricetick: float = ASHARE_BACKTEST_DEFAULTS["pricetick"]
    capital: float = ASHARE_BACKTEST_DEFAULTS["capital"]


@dataclass
class BatchBacktestRow:
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
) -> JobResult:
    items = rows_to_stock_items(rows)
    if not items:
        return JobResult(success=False, message="没有可下载的有效标的")

    start_dt = start or datetime(2020, 1, 1)
    end_dt = end or datetime.now()
    success = 0
    failed: list[str] = []

    for index, item in enumerate(items, start=1):
        try:
            download_bars(
                symbol=item.symbol,
                exchange=item.exchange,
                interval=Interval.DAILY,
                start=start_dt,
                end=end_dt,
                output=lambda _msg: None,
            )
            success += 1
        except Exception:
            failed.append(item.vt_symbol)
        if index < len(items) and delay > 0:
            time.sleep(delay)

    if failed:
        return JobResult(
            success=False,
            message=f"日 K 下载：成功 {success}，失败 {len(failed)}（{', '.join(failed[:5])}）",
        )
    return JobResult(success=True, message=f"已下载 {success} 只日 K")


def load_batch_backtest_defaults() -> BatchBacktestParams:
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
    from vnpy_ctabacktester.engine import APP_NAME, BacktesterEngine

    engine = main_engine.get_engine(APP_NAME)
    if not isinstance(engine, BacktesterEngine):
        raise RuntimeError("回测引擎未加载")

    items = rows_to_stock_items(rows)
    if not items:
        return []

    results: list[BatchBacktestRow] = []
    setting: dict[str, Any] = {}

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


def persist_batch_backtest_results(
    params: BatchBacktestParams,
    rows: list[BatchBacktestRow],
) -> str:
    """批量回测结果落库，返回 batch_id。"""
    from vnpy_ashare.backtest.run_store import save_backtest_run

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
            source="batch_screener",
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
