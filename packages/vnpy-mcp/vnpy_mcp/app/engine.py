"""MCP Provider 加载与管理（对标 vnpy_skills.engine.SkillEngine）。"""

from __future__ import annotations

import traceback
from typing import Any

from dotenv import load_dotenv

from vnpy_common.paths import ENV_FILE
from vnpy_mcp.base import McpProvider
from vnpy_mcp.client import McpClientError, call_remote_tool, list_remote_tools
from vnpy_mcp.config import load_all_mcp_servers
from vnpy_mcp.providers.remote import RemoteMcpProvider
from vnpy_skills.base import ToolSpec

APP_NAME = "MCP"


class McpEngine:
    """从 ``mcp/`` 目录加载远端 MCP Provider，发现工具并代理执行。"""

    def __init__(self) -> None:
        self.providers: dict[str, McpProvider] = {}
        self._tool_index: dict[str, str] = {}
        self._connect_errors: dict[str, str] = {}

    def load_all(self) -> None:
        load_dotenv(ENV_FILE, override=False)
        self.providers.clear()
        for _name, config in load_all_mcp_servers().items():
            provider = RemoteMcpProvider(config)
            provider.on_init()
            self.providers[provider.provider_name] = provider

    def init_providers(self) -> list[str]:
        """连接可用 Provider 并发现工具，返回已启用名称列表。"""
        self._tool_index.clear()
        self._connect_errors.clear()
        enabled: list[str] = []

        for name, provider in sorted(self.providers.items()):
            if not provider.available:
                continue
            try:
                tools = list_remote_tools(provider.url, provider.headers)
                provider.set_tools(tools)
                enabled.append(name)
                for tool in tools:
                    self._tool_index[provider.prefixed_name(tool.name)] = name
            except McpClientError as ex:
                provider.mark_disconnected()
                self._connect_errors[name] = str(ex)
                print(f"MCP Provider {name} 连接失败: {ex}")
            except Exception:
                provider.mark_disconnected()
                msg = traceback.format_exc()
                self._connect_errors[name] = msg
                print(f"MCP Provider {name} 连接失败:\n{msg}")

        return enabled

    def reload_providers(self) -> list[str]:
        self.load_all()
        return self.init_providers()

    def get_enabled_providers(self) -> list[McpProvider]:
        return [p for p in self.providers.values() if p.connected]

    def get_connect_errors(self) -> dict[str, str]:
        return dict(self._connect_errors)

    def build_mcp_prompt(self) -> str:
        providers = self.get_enabled_providers()
        if not providers:
            return ""

        parts = [
            "【已连接 MCP 服务】",
            "以下工具来自远端 MCP Server，通过 mcp_<provider>_<tool> 名称调用。",
            "涉及实时行情、K 线、板块等数据时必须调用工具，禁止编造。",
            "",
        ]
        for provider in providers:
            parts.append(provider.prompt_section())
            parts.append("")

        errors = self._connect_errors
        unavailable = [p for p in self.providers.values() if p.available and not p.connected and p.provider_name in errors]
        if unavailable:
            parts.append("【MCP 连接失败】")
            for provider in unavailable:
                parts.append(f"- {provider.provider_name}: {errors[provider.provider_name][:200]}")
            parts.append("")

        return "\n".join(parts).strip()

    def get_openai_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for provider in self.get_enabled_providers():
            for spec in provider.to_tool_specs():
                tools.append(spec.to_openai_tool())
        return tools

    def get_tool_specs(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for provider in self.get_enabled_providers():
            specs.extend(provider.to_tool_specs())
        return specs

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        owner = self._tool_index.get(name)
        if owner is None:
            return f'{{"error": "未注册的 MCP 工具: {name}"}}'

        provider = self.providers.get(owner)
        if provider is None or not provider.connected:
            return f'{{"error": "MCP Provider 未连接: {owner}"}}'

        original = provider.strip_prefix(name)
        if original is None:
            return f'{{"error": "工具名前缀不匹配: {name}"}}'

        try:
            result = call_remote_tool(
                provider.url,
                provider.headers,
                original,
                arguments,
            )
            return provider.format_tool_result(result)
        except McpClientError as ex:
            return f'{{"error": "{ex}"}}'
        except Exception as ex:
            return f'{{"error": "{ex}"}}'

    def provider_names(self) -> list[str]:
        return [p.provider_name for p in self.get_enabled_providers()]
