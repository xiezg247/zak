"""交易记账、计划、持仓与策略信号领域模型。"""

from vnpy_ashare.domain.trading.exit import ExitRuleHit, ExitSignal, OvernightExitEvaluation, RuleStatus
from vnpy_ashare.domain.trading.journal import JournalSide, TradeJournalEntry
from vnpy_ashare.domain.trading.journal_report import JournalReport
from vnpy_ashare.domain.trading.plan import (
    TradeMode,
    TradingPlanRecord,
    TradingPlanStatus,
    TradingPlanSymbolRecord,
)
from vnpy_ashare.domain.trading.plan_check import BuyPlanCheckResult
from vnpy_ashare.domain.trading.position import (
    PositionRecord,
    PositionSnapshot,
    build_position_snapshot,
    compute_unrealized_pnl,
    dist_exit_pct,
    position_row_sort_key,
    position_t1_locked,
)
from vnpy_ashare.domain.trading.risk import (
    BookPnlSummary,
    CombinedRiskGateSnapshot,
    GroupPositionSummary,
    PositionSizeResult,
    RiskGateSnapshot,
    RiskGateState,
)
from vnpy_ashare.domain.trading.signal_benchmark import (
    SIGNAL_BENCHMARK_LOOKBACK,
    SIGNAL_BENCHMARK_SYMBOL,
    SIGNAL_BENCHMARK_TS_CODE,
)
from vnpy_ashare.domain.trading.signal_snapshot import (
    SIGNAL_COLUMN_KEYS,
    SIGNAL_LABELS,
    SignalKind,
    SignalSnapshot,
    detect_signal_transitions,
    signal_as_of_stale,
    signal_missing_kline,
)

__all__ = [
    "BookPnlSummary",
    "BuyPlanCheckResult",
    "CombinedRiskGateSnapshot",
    "ExitRuleHit",
    "ExitSignal",
    "GroupPositionSummary",
    "JournalReport",
    "JournalSide",
    "OvernightExitEvaluation",
    "PositionRecord",
    "PositionSizeResult",
    "PositionSnapshot",
    "RiskGateSnapshot",
    "RiskGateState",
    "RuleStatus",
    "SIGNAL_BENCHMARK_LOOKBACK",
    "SIGNAL_BENCHMARK_SYMBOL",
    "SIGNAL_BENCHMARK_TS_CODE",
    "SIGNAL_COLUMN_KEYS",
    "SIGNAL_LABELS",
    "SignalKind",
    "SignalSnapshot",
    "TradeJournalEntry",
    "TradeMode",
    "TradingPlanRecord",
    "TradingPlanStatus",
    "TradingPlanSymbolRecord",
    "build_position_snapshot",
    "compute_unrealized_pnl",
    "detect_signal_transitions",
    "dist_exit_pct",
    "position_row_sort_key",
    "position_t1_locked",
    "signal_as_of_stale",
    "signal_missing_kline",
]
