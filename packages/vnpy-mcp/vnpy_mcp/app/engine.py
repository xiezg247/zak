"""MCP Provider 加载与管理（对标 vnpy_skills.app.engine.SkillEngine）。"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from dotenv import load_dotenv

from vnpy_common.paths import ENV_FILE
from vnpy_mcp.config.settings import load_all_mcp_servers
from vnpy_mcp.domain.provider import McpProvider
from vnpy_mcp.remote.client import McpClientError, call_remote_tool, list_remote_tools
from vnpy_mcp.remote.provider import RemoteMcpProvider
from vnpy_skills.domain.template import ToolSpec

APP_NAME = "MCP"
logger = logging.getLogger(__name__)


class McpEngine:
    """从 ``mcp/`` 目录加载远端 MCP Provider，发现工具并代理执行。"""

    def __init__(self) -> None:
        self.providers: dict[str, McpProvider] = {}
        self._tool_index: dict[str, str] = {}
        self._connect_errors: dict[str, str] = {}
        self._providers_initialized = False

    @property
    def providers_initialized(self) -> bool:
        return self._providers_initialized

    def load_all(self) -> None:
        load_dotenv(ENV_FILE, override=False)
        self.providers.clear()
        self._tool_index.clear()
        self._connect_errors.clear()
        self._providers_initialized = False
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
                logger.warning("MCP Provider %s 连接失败: %s", name, ex)
            except Exception:
                provider.mark_disconnected()
                msg = traceback.format_exc()
                self._connect_errors[name] = msg
                logger.warning("MCP Provider %s 连接失败:\n%s", name, msg)

        self._providers_initialized = True
        return enabled

    def ensure_providers(self) -> list[str]:
        """按需连接：已初始化则直接返回，否则执行 init_providers。"""
        if self._providers_initialized:
            return [name for name, provider in self.providers.items() if provider.connected]
        return self.init_providers()

    def reload_providers(self) -> list[str]:
        self.load_all()
        return self.init_providers()

    def get_enabled_providers(self) -> list[McpProvider]:
        return [p for p in self.providers.values() if p.connected]

    def get_connect_errors(self) -> dict[str, str]:
        return dict(self._connect_errors)

    def build_mcp_prompt(self) -> str:
        """已废弃：原始 MCP 工具不向 LLM 暴露，请用 ``build_internal_status_note``。"""
        return self.build_internal_status_note()

    def build_internal_status_note(self) -> str:
        """MCP 连接状态摘要（不含工具清单，供 system 提示）。"""
        providers = self.get_enabled_providers()
        errors = self.get_connect_errors()
        if providers:
            names = "、".join(p.provider_name for p in providers)
            return (
                f"【MCP 后端】已连接 {names}，仅供 Skill 内部调用"
                "（如 diagnose_stock、screen_by_pattern、historical_pattern_summary 兜底）。"
                "对话中请使用 Skill 工具，勿直接调用 mcp_* 工具。"
            )
        if errors:
            detail = next(iter(errors.values()), "连接失败")[:120]
            return f"【MCP 后端】通达信未连接，综合诊断与形态选股将降级本地能力。（{detail}）请检查 mcp/mcp.json 中的 tdx-api-key。"
        return ""

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
