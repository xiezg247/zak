"""个股分析弹窗：指标抽取、质量提示与资金流摘要。

实现已迁至 ``services.stock.context``；本模块保留 re-export。
"""

from vnpy_ashare.services.stock.context import (
    DiagnoseMetrics,
    MoneyflowDayRow,
    MoneyflowProfile,
    build_analysis_ai_context,
    build_financial_quality_hints,
    build_moneyflow_profile,
    compute_relative_returns,
    extract_diagnose_metrics,
    format_technical_summary,
    signal_summary_label,
)

__all__ = [
    "DiagnoseMetrics",
    "MoneyflowDayRow",
    "MoneyflowProfile",
    "build_analysis_ai_context",
    "build_financial_quality_hints",
    "build_moneyflow_profile",
    "compute_relative_returns",
    "extract_diagnose_metrics",
    "format_technical_summary",
    "signal_summary_label",
]
