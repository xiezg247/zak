"""回测与批量回测 UI。

目录约定：
- ``pages/``：单只回测、批量对比页
- ``flow/``：批量回测流程
- ``chart/``：回测图表
- ``table/``：批量对比表
"""

from vnpy_ashare.ui.backtest.flow import BatchBacktestFlow
from vnpy_ashare.ui.backtest.pages import BacktesterWidget, BatchBacktestPageWidget

__all__ = ["BacktesterWidget", "BatchBacktestFlow", "BatchBacktestPageWidget"]
