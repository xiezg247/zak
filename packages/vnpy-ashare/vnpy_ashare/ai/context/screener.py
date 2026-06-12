"""选股页 AI 上下文（委托 ScreeningService）。"""

from __future__ import annotations

from vnpy_ashare.app.engine_access import get_screening_service
from vnpy_ashare.services.screening_service import publish_screener_page_context


def sync_screener_page_context(main_engine=None) -> None:
    """选股页激活时同步 AI 上下文；优先 ScreeningService，无 Engine 时走模块函数。"""
    service = get_screening_service(main_engine)
    if service is not None:
        service.publish_page_context()
    else:
        publish_screener_page_context()


def build_ask_ai_prompt_for_run(run_id: str, condition: str) -> str:
    """生成「发给 AI 解读历史选股」的预填文案。"""
    condition = condition.strip() or "（未知条件）"
    return f"请解读这次选股历史（条件：{condition}）。分析板块分布、与上次变动差异及技术面快照后解读，不要编造未在结果中的指标。"
