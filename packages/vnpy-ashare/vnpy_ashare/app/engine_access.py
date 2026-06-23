"""AshareEngine 与 Service 访问辅助。

UI / Worker 获取业务能力的统一入口，避免页面散落 ``getattr(engine, "xxx_service")``。

典型链路::

    QuotesPage._get_quote_service()
        → engine_access.get_quote_service(main_engine)
        → AshareEngine.quote_service
        → context_store（AI 上下文写入）

优先使用下方类型化 getter；``get_service(name)`` 用于尚未封装 getter 的 Service。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from vnpy_ashare.app.constants import APP_NAME

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.app.engine import AshareEngine
    from vnpy_ashare.services.analysis import AnalysisService
    from vnpy_ashare.services.backtest import BacktestService
    from vnpy_ashare.services.bar import BarService
    from vnpy_ashare.services.feed import FeedService
    from vnpy_ashare.services.financial import FinancialService
    from vnpy_ashare.services.note import NoteService
    from vnpy_ashare.services.position import PositionService
    from vnpy_ashare.services.quote import QuoteService
    from vnpy_ashare.services.screening import ScreeningService
    from vnpy_ashare.services.sector_flow import SectorFlowService
    from vnpy_ashare.services.sentiment import SentimentService
    from vnpy_ashare.services.stock_analysis import StockAnalysisService
    from vnpy_ashare.services.watchlist import WatchlistService


def get_ashare_engine(main_engine: MainEngine | None) -> AshareEngine | None:
    """从 MainEngine 获取 AshareEngine；未注册或类型不符时返回 None。"""
    if main_engine is None:
        return None
    engine = main_engine.get_engine(APP_NAME)
    if engine is None or not hasattr(engine, "quote_service"):
        return None
    return cast("AshareEngine", engine)


def get_service(main_engine: MainEngine | None, name: str):
    """按属性名获取 Service；新代码优先使用下方类型化 getter。"""
    engine = get_ashare_engine(main_engine)
    if engine is None:
        return None
    return getattr(engine, name, None)


def get_analysis_service(main_engine: MainEngine | None) -> AnalysisService | None:
    """诊断聚合 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.analysis_service if engine is not None else None


def get_financial_service(main_engine: MainEngine | None) -> FinancialService | None:
    """个股财报 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.financial_service if engine is not None else None


def get_backtest_service(main_engine: MainEngine | None) -> BacktestService | None:
    """回测生命周期与摘要 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.backtest_service if engine is not None else None


def get_bar_service(main_engine: MainEngine | None) -> BarService | None:
    """K 线查询与数据管理页上下文 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.bar_service if engine is not None else None


def get_quote_service(main_engine: MainEngine | None) -> QuoteService | None:
    """行情查询与看盘页 AI 上下文 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.quote_service if engine is not None else None


def get_screening_service(main_engine: MainEngine | None) -> ScreeningService | None:
    """选股执行、历史与 AI 上下文 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.screening_service if engine is not None else None


def get_sentiment_service(main_engine: MainEngine | None) -> SentimentService | None:
    """恐贪指数 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.sentiment_service if engine is not None else None


def get_watchlist_service(main_engine: MainEngine | None) -> WatchlistService | None:
    """自选池 CRUD Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.watchlist_service if engine is not None else None


def get_note_service(main_engine: MainEngine | None) -> NoteService | None:
    """个股笔记 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.note_service if engine is not None else None


def get_feed_service(main_engine: MainEngine | None) -> FeedService | None:
    """信息流 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.feed_service if engine is not None else None


def get_position_service(main_engine: MainEngine | None) -> PositionService | None:
    """自选持仓记账 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.position_service if engine is not None else None


def get_stock_analysis_service(main_engine: MainEngine | None) -> StockAnalysisService | None:
    """个股分析弹窗 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.stock_analysis_service if engine is not None else None


def get_sector_flow_service(main_engine: MainEngine | None) -> SectorFlowService | None:
    """板块资金监控 Service。"""
    engine = get_ashare_engine(main_engine)
    return engine.sector_flow_service if engine is not None else None


def require_service(main_engine: MainEngine | None, name: str):
    """获取 Service，不存在时抛出 RuntimeError。"""
    service = get_service(main_engine, name)
    if service is None:
        raise RuntimeError(f"Service 未就绪：{name}")
    return service
