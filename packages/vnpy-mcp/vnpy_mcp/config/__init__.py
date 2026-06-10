"""MCP 配置加载与内置 Provider 元数据。"""

from vnpy_mcp.config.registry import BUILTIN_MCP_PROVIDERS, McpProviderMeta
from vnpy_mcp.config.settings import (
    DEFAULT_MCP_DIR,
    DEFAULT_TDX_MCP_URL,
    MCP_CONFIG_FILENAME,
    McpServerConfig,
    get_mcp_server,
    list_mcp_server_names,
    load_all_mcp_servers,
    load_mcp_dir,
    resolve_mcp_config_paths,
    resolve_mcp_dir,
)

__all__ = [
    "BUILTIN_MCP_PROVIDERS",
    "DEFAULT_MCP_DIR",
    "DEFAULT_TDX_MCP_URL",
    "MCP_CONFIG_FILENAME",
    "McpProviderMeta",
    "McpServerConfig",
    "get_mcp_server",
    "list_mcp_server_names",
    "load_all_mcp_servers",
    "load_mcp_dir",
    "resolve_mcp_config_paths",
    "resolve_mcp_dir",
]
