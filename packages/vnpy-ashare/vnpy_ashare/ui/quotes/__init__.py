"""看盘页：QuotesPage 及其 controller、图表子组件。

目录约定：
- ``page/``：QuotesPage、布局 shell、配置、运行输出
- ``controllers/``：表格、数据、操作等 Controller
- ``table/``：列定义、Model、市场展示
- ``chart/``：ChartPanel、日 K / 分时 / 分 K
- ``panels/``：盘口、诊断、表格 loading
- ``watchlist_signals/``：自选策略信号区
- ``workers/``：后台 Worker
"""

from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

__all__ = ["QuotesPage"]
