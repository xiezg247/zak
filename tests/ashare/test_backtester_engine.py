"""AshareBacktesterEngine 在 vnpy chdir 到 ~/.vntrader 后仍能加载项目策略。"""

from __future__ import annotations

import os

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.utility import TRADER_DIR

from vnpy_ashare.backtest.strategy_filter import filter_ashare_strategy_names
from vnpy_ashare.backtest.app import AshareCtaBacktesterApp


def test_load_project_strategies_after_main_engine_chdir() -> None:
    os.chdir(TRADER_DIR)
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_app(AshareCtaBacktesterApp)

    engine = main_engine.get_engine("CtaBacktester")
    engine.init_engine()

    names = filter_ashare_strategy_names(engine.classes)
    assert "AshareDoubleMaStrategy" in names

    event_engine.stop()
