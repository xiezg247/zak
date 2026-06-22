"""A 股 App 引擎：注册 Service 层与定时任务调度。

挂载于 MainEngine（``APP_NAME = "Ashare"``），UI / Worker 经 ``engine_access`` 获取各 Service。
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine

from vnpy_ashare.app.constants import APP_NAME
from vnpy_ashare.notifications.service import NotificationService
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleTracker
from vnpy_ashare.scheduler.manager import TaskSchedulerManager
from vnpy_ashare.services.analysis import AnalysisService
from vnpy_ashare.services.backtest import BacktestService
from vnpy_ashare.services.bar import BarService
from vnpy_ashare.services.financial import FinancialService
from vnpy_ashare.services.note import NoteService
from vnpy_ashare.services.position import PositionService
from vnpy_ashare.services.quote import QuoteService
from vnpy_ashare.services.radar import RadarService
from vnpy_ashare.services.screening import ScreeningService
from vnpy_ashare.services.sector_flow import SectorFlowService
from vnpy_ashare.services.sentiment import SentimentService
from vnpy_ashare.services.stock_analysis import StockAnalysisService
from vnpy_ashare.services.watchlist import WatchlistService
from vnpy_ashare.trading.risk.gate import RiskGateEngine


class AshareEngine(BaseEngine):
    """A 股行情引擎（含定时任务调度与服务层）。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.scheduler = TaskSchedulerManager()

        self.bar_service = BarService(self)
        self.quote_service = QuoteService(self)
        self.backtest_service = BacktestService(self)
        self.screening_service = ScreeningService(self)
        self.radar_service = RadarService(self)
        self.watchlist_service = WatchlistService(self)
        self.position_service = PositionService(self)
        self.note_service = NoteService(self)
        self.analysis_service = AnalysisService(self)
        self.financial_service = FinancialService(self)
        self.sentiment_service = SentimentService(self)
        self.stock_analysis_service = StockAnalysisService(self)
        self.sector_flow_service = SectorFlowService(self)

        self.emotion_cycle_tracker = EmotionCycleTracker()
        self.risk_gate_engine = RiskGateEngine()
        self.notification_service = NotificationService(self)
        self.scheduler.add_job_finished_hook(self.notification_service.on_job_finished)

    def close(self) -> None:
        self.notification_service.shutdown()
        self.scheduler.shutdown()
        super().close()
