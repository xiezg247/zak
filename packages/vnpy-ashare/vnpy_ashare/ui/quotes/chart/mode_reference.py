"""兼容 re-export：实现已迁至 trading.signals.mode_reference。"""

from vnpy_ashare.trading.signals.mode_reference import (
    MODE_BAND_COLOR,
    MODE_DIP_COLOR,
    MODE_LIMIT_COLOR,
    MODE_MA_COLOR,
    MODE_MUTED_COLOR,
    MODE_SUPPORT_COLOR,
    IntradayModeKind,
    ModeReferenceLine,
    build_intraday_mode_reference_lines,
    mode_reference_window_hint,
    resolve_intraday_mode_kind,
)

__all__ = [
    "MODE_BAND_COLOR",
    "MODE_DIP_COLOR",
    "MODE_LIMIT_COLOR",
    "MODE_MA_COLOR",
    "MODE_MUTED_COLOR",
    "MODE_SUPPORT_COLOR",
    "IntradayModeKind",
    "ModeReferenceLine",
    "build_intraday_mode_reference_lines",
    "mode_reference_window_hint",
    "resolve_intraday_mode_kind",
]
