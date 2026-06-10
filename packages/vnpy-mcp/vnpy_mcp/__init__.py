"""vnpy_mcp：远端 MCP 工具框架。"""

from vnpy_mcp.app.engine import APP_NAME, McpEngine
from vnpy_mcp.config import (
    DEFAULT_MCP_DIR,
    DEFAULT_TDX_MCP_URL,
    McpServerConfig,
    load_all_mcp_servers,
)
from vnpy_mcp.domain import McpProvider, McpToolInfo
from vnpy_mcp.remote import McpClientError, RemoteMcpProvider

__all__ = [
    "APP_NAME",
    "DEFAULT_MCP_DIR",
    "DEFAULT_TDX_MCP_URL",
    "McpClientError",
    "McpEngine",
    "McpProvider",
    "McpServerConfig",
    "McpToolInfo",
    "RemoteMcpProvider",
    "load_all_mcp_servers",
]
