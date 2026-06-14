"""A 股 App 引擎：注册 Service 层与定时任务调度。

挂载于 MainEngine（``APP_NAME = "Ashare"``），UI / Worker 经 ``engine_access`` 获取各 Service。
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine

from vnpy_ashare.scheduler import TaskSchedulerManager
from vnpy_ashare.services import (
    AnalysisService,
    BacktestService,
    BarService,
    FinancialService,
    NoteService,
    PositionService,
    QuoteService,
    ScreeningService,
    SentimentService,
    StockAnalysisService,
    WatchlistService,
)

APP_NAME = "Ashare"


class AshareEngine(BaseEngine):
    """A 股行情引擎（含定时任务调度与服务层）。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.scheduler = TaskSchedulerManager()

        self.bar_service = BarService(self)
        self.quote_service = QuoteService(self)
        self.backtest_service = BacktestService(self)
        self.screening_service = ScreeningService(self)
        self.watchlist_service = WatchlistService(self)
        self.position_service = PositionService(self)
        self.note_service = NoteService(self)
        self.analysis_service = AnalysisService(self)
        self.financial_service = FinancialService(self)
        self.sentiment_service = SentimentService(self)
        self.stock_analysis_service = StockAnalysisService(self)

    def close(self) -> None:
        self.scheduler.shutdown()
        super().close()
