"""从 JSON 配置实例化的通用远端 MCP Provider。"""

from __future__ import annotations

from vnpy_mcp.base import McpProvider
from vnpy_mcp.config import McpServerConfig, get_mcp_server


class RemoteMcpProvider(McpProvider):
    """``mcp/*.json`` 或 legacy ``mcp.json`` 中声明的 Streamable HTTP MCP。"""

    def __init__(self, config: McpServerConfig) -> None:
        super().__init__()
        self.provider_name = config.name
        self._config = config
        self.description = config.display_description

    def on_init(self) -> None:
        latest = get_mcp_server(self.provider_name)
        if latest is not None:
            self._config = latest
            self.description = latest.display_description

    @property
    def config(self) -> McpServerConfig:
        return self._config

    @property
    def available(self) -> bool:
        return self._config.available

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def url(self) -> str:
        return self._config.url

    @property
    def headers(self) -> dict[str, str]:
        return dict(self._config.headers)

    @property
    def missing_env(self) -> list[str]:
        return list(self._config.missing_hints)
