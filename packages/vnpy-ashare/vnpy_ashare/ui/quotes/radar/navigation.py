"""雷达页跨页导航：查找 shell host 与打开能力探测。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy.trader.ui import QtWidgets

_HOST_MARKERS = (
    "open_screener_run",
    "open_sector_flow",
    "open_screener_radar_resonance",
)


@dataclass(frozen=True, slots=True)
class NavReject:
    message: str
    level: str = "warning"


def find_shell_host(start: QtWidgets.QWidget | None) -> QtWidgets.QWidget | None:
    """沿 parent 链查找具备跨页打开能力的主窗口。"""
    widget = start
    while widget is not None:
        if any(hasattr(widget, name) for name in _HOST_MARKERS):
            return widget
        widget = widget.parentWidget()
    return None


def require_host_method(
    host: Any,
    method: str,
    *,
    fail_message: str,
) -> NavReject | None:
    if host is None or not hasattr(host, method):
        return NavReject(fail_message)
    return None


def sector_flow_call_kwargs(
    sector_ids: list[str] | None,
    *,
    rotation: bool = False,
) -> dict[str, object]:
    """构造 ``open_sector_flow`` 调用参数。"""
    ids = sector_ids if sector_ids else None
    if rotation:
        return {
            "sector_ids": ids,
            "tab": "rotation",
            "sector_kind": "industry",
        }
    return {"sector_ids": ids}
