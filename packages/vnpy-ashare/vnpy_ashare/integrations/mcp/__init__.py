"""MCP 外部集成（通达信问小达等）。"""

from vnpy_ashare.integrations.mcp.intraday_flow import (
    bind_mcp_intraday_flow,
    fetch_intraday_moneyflow_map,
    mcp_intraday_flow_enabled,
)

__all__ = [
    "bind_mcp_intraday_flow",
    "fetch_intraday_moneyflow_map",
    "mcp_intraday_flow_enabled",
]
