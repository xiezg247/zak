from vnpy.event import EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine

from vnpy_ashare.scheduler import TaskSchedulerManager

APP_NAME = "Ashare"


class AshareEngine(BaseEngine):
    """A 股行情引擎（含定时任务调度）。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(main_engine, event_engine, APP_NAME)
        self.scheduler = TaskSchedulerManager()
        self.scheduler.start()

    def close(self) -> None:
        self.scheduler.shutdown()
        super().close()
