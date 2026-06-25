"""Universe 列表加载与同步 Worker。"""

from __future__ import annotations

import logging

from vnpy.trader.ui import QtCore

from vnpy_ashare.data.bars import (
    count_downloaded_stocks,
    load_downloaded_stocks,
    load_downloaded_stocks_page,
    load_watchlist,
    search_downloaded_stocks_page,
)
from vnpy_ashare.storage.universe import load_universe, sync_universe
from vnpy_ashare.ui.quotes.workers.quotes_workers.models import UniverseLoadResult

logger = logging.getLogger(__name__)


class UniverseLoadWorker(QtCore.QThread):
    """加载 universe 列表（全部 A 股 / 自选池 / 已下载）。"""

    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(
        self,
        scope: str,
        *,
        local_scope: str = "daily",
        offset: int = 0,
        limit: int | None = None,
        keyword: str = "",
    ) -> None:
        super().__init__()
        self.scope = scope
        self.local_scope = local_scope
        self.offset = max(offset, 0)
        self.limit = limit
        self.keyword = keyword.strip()
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            if self.scope == "全部A股":
                stocks = load_universe(allow_sync=False)
                total = len(stocks)
            elif self.scope == "自选池" or self.scope == "策略监控":
                stocks = load_watchlist()
                total = len(stocks)
            elif self.limit is not None:
                if self.keyword:
                    stocks, total = search_downloaded_stocks_page(
                        scope=self.local_scope,
                        keyword=self.keyword,
                        offset=self.offset,
                        limit=self.limit,
                    )
                else:
                    total = count_downloaded_stocks(scope=self.local_scope)
                    stocks = load_downloaded_stocks_page(
                        scope=self.local_scope,
                        offset=self.offset,
                        limit=self.limit,
                    )
            else:
                stocks = load_downloaded_stocks(scope=self.local_scope)
                total = len(stocks)
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(UniverseLoadResult(items=stocks, total=total))
        except Exception as ex:
            logger.exception(
                "列表加载失败 scope=%s local_scope=%s offset=%s limit=%s keyword=%r",
                self.scope,
                self.local_scope,
                self.offset,
                self.limit,
                self.keyword,
            )
            self.failed.emit(str(ex))


class UniverseSyncWorker(QtCore.QThread):
    """同步 A 股列表到本地 SQLite。"""

    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            path = sync_universe(force=True)
            if self._cancel_requested:
                self.failed.emit("已取消")
                return
            self.finished.emit(str(path))
        except Exception as ex:
            logger.exception("A 股列表同步失败")
            self.failed.emit(str(ex))
