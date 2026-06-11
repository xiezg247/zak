"""批量回测子进程 worker（独立 BacktestingEngine，避免共享 MainEngine 状态）。"""

from __future__ import annotations

import importlib
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy.trader.constant import Interval

from vnpy_common.paths import PROJECT_ROOT, resolve_project_root

_STRATEGY_PRIORITY = ("ashare_template.py",)
_WORKER_BOOTSTRAPPED = False
_STRATEGY_SKIP = frozenset({"__init__", "registry", "signals"})


@dataclass(frozen=True)
class BacktestTask:
    """可序列化的单标的回测任务。"""

    vt_symbol: str
    name: str
    class_name: str
    interval: str
    start: str
    end: str
    rate: float
    slippage: float
    size: int
    pricetick: float
    capital: float
    setting: dict[str, Any]


def batch_backtest_max_workers(*, item_count: int) -> int:
    """并行 worker 数上限（可通过 BATCH_BACKTEST_MAX_WORKERS 配置）。"""
    raw = os.getenv("BATCH_BACKTEST_MAX_WORKERS", "4").strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = 4
    configured = max(1, min(configured, 8))
    cpu = os.cpu_count() or 1
    return min(configured, item_count, cpu)


def _ensure_worker_runtime() -> None:
    """子进程 spawn 后补齐项目根路径与 vnpy 数据库配置。"""
    global _WORKER_BOOTSTRAPPED
    if _WORKER_BOOTSTRAPPED:
        return
    root = resolve_project_root()
    os.environ.setdefault("ZAK_PROJECT_ROOT", str(root))
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    os.chdir(root)
    try:
        from vnpy_ashare.config.vt_settings import reload_vnpy_settings

        reload_vnpy_settings()
    except Exception:
        pass
    _WORKER_BOOTSTRAPPED = True


def resolve_strategy_class(class_name: str) -> type:
    """从项目 strategies/ 目录解析策略类。"""
    strategies_dir = PROJECT_ROOT / "strategies"
    if not strategies_dir.is_dir():
        raise ValueError(f"未找到策略目录：{strategies_dir}")

    searched: set[str] = set()
    for filename in _STRATEGY_PRIORITY:
        stem = filename.removesuffix(".py")
        if stem in searched:
            continue
        searched.add(stem)
        cls = _load_strategy_from_module(stem, class_name)
        if cls is not None:
            return cls

    for path in sorted(strategies_dir.glob("*.py")):
        stem = path.stem
        if stem in _STRATEGY_SKIP or stem in searched:
            continue
        cls = _load_strategy_from_module(stem, class_name)
        if cls is not None:
            return cls

    raise ValueError(f"未找到策略：{class_name}")


def _load_strategy_from_module(module_stem: str, class_name: str) -> type | None:
    module = importlib.import_module(f"strategies.{module_stem}")
    candidate = getattr(module, class_name, None)
    if candidate is None or not isinstance(candidate, type):
        return None
    return candidate


def run_single_backtest_task(task: BacktestTask) -> dict[str, Any]:
    """在子进程或主线程执行单标的回测，返回 BatchBacktestRow 字段结构的 dict。"""
    from vnpy_ctastrategy.backtesting import BacktestingEngine, BacktestingMode

    _ensure_worker_runtime()
    row: dict[str, Any] = {
        "vt_symbol": task.vt_symbol,
        "name": task.name,
        "total_return": None,
        "max_drawdown": None,
        "sharpe_ratio": None,
        "total_trade_count": None,
        "error": "",
    }
    try:
        strategy_class = resolve_strategy_class(task.class_name)
        engine = BacktestingEngine()
        mode = BacktestingMode.TICK if task.interval == Interval.TICK.value else BacktestingMode.BAR
        engine.set_parameters(
            vt_symbol=task.vt_symbol,
            interval=task.interval,
            start=datetime.fromisoformat(task.start),
            end=datetime.fromisoformat(task.end),
            rate=task.rate,
            slippage=task.slippage,
            size=task.size,
            pricetick=task.pricetick,
            capital=task.capital,
            mode=mode,
        )
        engine.add_strategy(strategy_class, dict(task.setting))
        engine.load_data()
        if not engine.history_data:
            row["error"] = "历史数据为空"
            return row
        engine.run_backtesting()
        engine.calculate_result()
        stats = engine.calculate_statistics(output=False) or {}
        row["total_return"] = _to_float(stats.get("total_return"))
        row["max_drawdown"] = _to_float(stats.get("max_drawdown"))
        row["sharpe_ratio"] = _to_float(stats.get("sharpe_ratio"))
        trade_count = stats.get("total_trade_count")
        row["total_trade_count"] = int(trade_count) if trade_count is not None else None
    except Exception as ex:
        row["error"] = str(ex) or traceback.format_exc(limit=2)
    return row


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        text = str(value).replace("%", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return None


def task_from_params(item, params, *, class_name: str, setting: dict[str, Any]) -> BacktestTask:
    interval = params.interval.value if hasattr(params.interval, "value") else str(params.interval)
    return BacktestTask(
        vt_symbol=item.vt_symbol,
        name=item.name,
        class_name=class_name,
        interval=interval,
        start=params.start.strftime("%Y-%m-%d"),
        end=params.end.strftime("%Y-%m-%d"),
        rate=params.rate,
        slippage=params.slippage,
        size=params.size,
        pricetick=params.pricetick,
        capital=int(params.capital),
        setting=dict(setting),
    )
