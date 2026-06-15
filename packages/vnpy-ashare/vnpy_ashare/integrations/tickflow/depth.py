"""TickFlow REST 五档盘口。"""

from __future__ import annotations

from tickflow._exceptions import APIError

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.integrations.tickflow.quotes import get_tickflow_client
from vnpy_ashare.quotes.core.depth_snapshot import DepthSnapshot


class DepthPermissionError(Exception):
    """无市场深度 REST 权限（403）。"""


def fetch_depth_from_tickflow(item: StockItem) -> DepthSnapshot:
    client = get_tickflow_client()
    try:
        data = client.depth.get(item.tickflow_symbol)
    except APIError as ex:
        if ex.status_code == 403:
            raise DepthPermissionError(ex.message) from ex
        raise
    return DepthSnapshot.from_tickflow(data)
