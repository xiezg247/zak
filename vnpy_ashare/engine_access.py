"""AshareEngine 与 Service 访问辅助。

UI / Worker 获取业务能力的统一入口，避免页面散落 ``getattr(engine, "xxx_service")``。

典型链路::

    QuotesPage._get_quote_service()
        → engine_access.get_quote_service(main_engine)
        → AshareEngine.quote_service
        → context_store（AI 上下文写入）

新代码请优先使用下方类型化 getter；``get_service(name)`` 仅用于尚未封装 getter 的旧路径。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.engine import AshareEngine
    from vnpy_ashare.services.analysis_service import AnalysisService
    from vnpy_ashare.services.backtest_service import BacktestService
    from vnpy_ashare.services.bar_service import BarService
    from vnpy_ashare.services.quote_service import QuoteService
    from vnpy_ashare.services.screening_service import ScreeningService
    from vnpy_ashare.services.sentiment_service import SentimentService
    from vnpy_ashare.services.watchlist_service import WatchlistService


def get_ashare_engine(main_engine: MainEngine | None) -> AshareEngine | None:
    if main_engine is None:
        return None
    from vnpy_ashare.engine import APP_NAME, AshareEngine

    engine = main_engine.get_engine(APP_NAME)
    if isinstance(engine, AshareEngine):
        return engine
    return None


def get_service(main_engine: MainEngine | None, name: str):
    """按属性名获取 Service；新代码优先使用下方类型化 getter。"""
    engine = get_ashare_engine(main_engine)
    if engine is None:
        return None
    return getattr(engine, name, None)


def get_analysis_service(main_engine: MainEngine | None) -> AnalysisService | None:
    engine = get_ashare_engine(main_engine)
    return engine.analysis_service if engine is not None else None


def get_backtest_service(main_engine: MainEngine | None) -> BacktestService | None:
    engine = get_ashare_engine(main_engine)
    return engine.backtest_service if engine is not None else None


def get_bar_service(main_engine: MainEngine | None) -> BarService | None:
    engine = get_ashare_engine(main_engine)
    return engine.bar_service if engine is not None else None


def get_quote_service(main_engine: MainEngine | None) -> QuoteService | None:
    engine = get_ashare_engine(main_engine)
    return engine.quote_service if engine is not None else None


def get_screening_service(main_engine: MainEngine | None) -> ScreeningService | None:
    engine = get_ashare_engine(main_engine)
    return engine.screening_service if engine is not None else None


def get_sentiment_service(main_engine: MainEngine | None) -> SentimentService | None:
    engine = get_ashare_engine(main_engine)
    return engine.sentiment_service if engine is not None else None


def get_watchlist_service(main_engine: MainEngine | None) -> WatchlistService | None:
    engine = get_ashare_engine(main_engine)
    return engine.watchlist_service if engine is not None else None


def require_service(main_engine: MainEngine | None, name: str):
    """获取 Service，不存在时抛出 RuntimeError。"""
    service = get_service(main_engine, name)
    if service is None:
        raise RuntimeError(f"Service 未就绪：{name}")
    return service
