"""本地 K 线控制器（组合各 mixin）。"""

from __future__ import annotations

from vnpy_ashare.ui.quotes.controllers.local_data.base import LocalDataControllerBase
from vnpy_ashare.ui.quotes.controllers.local_data.batch_ops import LocalDataBatchOpsMixin
from vnpy_ashare.ui.quotes.controllers.local_data.chart import LocalDataChartMixin
from vnpy_ashare.ui.quotes.controllers.local_data.download import LocalDataDownloadMixin
from vnpy_ashare.ui.quotes.controllers.local_data.meta import LocalDataMetaMixin


class LocalDataController(
    LocalDataDownloadMixin,
    LocalDataChartMixin,
    LocalDataBatchOpsMixin,
    LocalDataMetaMixin,
    LocalDataControllerBase,
):
    """本地 K 线元数据、下载、缺口检查与图表加载。"""
