"""选股页 AI 上下文（委托 ScreeningService）。"""

from __future__ import annotations

from vnpy_ashare.engine_access import get_screening_service
from vnpy_ashare.services.screening_service import publish_screener_page_context


def sync_screener_page_context(main_engine=None) -> None:
    service = get_screening_service(main_engine)
    if service is not None:
        service.publish_page_context()
    else:
        publish_screener_page_context()


def build_ask_ai_prompt_for_run(run_id: str, condition: str) -> str:
    """生成「发给 AI 解读历史选股」的预填文案。"""
    condition = condition.strip() or "（未知条件）"
    return (
        f"请解读这次选股历史（条件：{condition}）。"
        f'请调用 get_screening_context(run_id="{run_id}", batch_top_n=5) '
        "获取结果并解读前几只标的，不要编造未在结果中的指标。"
    )
