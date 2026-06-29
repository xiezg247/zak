"""策略监控页 feature：无盘中/复盘工具栏。"""

from __future__ import annotations

from unittest.mock import MagicMock

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes.features.strategy_monitor.page_feature import StrategyMonitorPageFeature
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE


def test_strategy_monitor_feature_skips_layout_preset_toolbar() -> None:
    page = MagicMock()
    page.page_name = STRATEGY_MONITOR_PAGE
    feature = StrategyMonitorPageFeature(page)
    toolbar = QtWidgets.QHBoxLayout()

    feature.prepend_toolbar_widgets(toolbar)

    assert getattr(feature, "layout_preset_combo", None) is None
