"""数据管理页 AI 上下文（委托 BarService）。"""

from __future__ import annotations

from vnpy_ashare.app.engine_access import get_service
from vnpy_ashare.services.bar_service import publish_data_manager_page_context


def sync_data_manager_context(main_engine=None) -> None:
    service = get_service(main_engine, "bar_service")
    if service is not None:
        service.publish_data_manager_context()
    else:
        publish_data_manager_page_context()
