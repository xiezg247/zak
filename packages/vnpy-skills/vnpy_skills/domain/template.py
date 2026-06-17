"""AI 技能基类（对标 CtaTemplate / AShareTemplate）。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class ToolSpec(FrozenModel):
    """OpenAI Function Calling 工具定义。"""

    name: str = Field(description="工具名称")
    description: str = Field(description="工具说明")
    parameters: dict[str, Any] = Field(description="JSON Schema 参数")
    handler: str | None = Field(default=None, description="处理函数名（默认同 name）")

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class SkillTemplate(ABC):
    """
    AI 技能基类。

    子类需定义 skill_name、description，并实现 register_tools / on_init。
    工具处理函数命名与 ToolSpec.name 一致，或通过 handler 指定。
    """

    skill_name: str = ""
    author: str = "zak"
    description: str = ""

    def __init__(self) -> None:
        self._tools: list[ToolSpec] = []
        self._handlers: dict[str, Callable[..., str]] = {}
        self._services: dict[str, Any] = {}

    def on_init(self) -> None:
        """初始化（检查 API Key、预热客户端等）。"""
        pass

    @property
    def available(self) -> bool:
        """技能是否可用（如缺少 Token 则不可用）。"""
        return True

    @abstractmethod
    def register_tools(self) -> list[ToolSpec]:
        """注册本技能提供的工具列表。"""

    def setup(self) -> None:
        """加载工具并绑定处理函数。"""
        self._tools = self.register_tools()
        self._handlers = {}
        for spec in self._tools:
            handler_name = spec.handler or spec.name
            handler = getattr(self, handler_name, None)
            if handler is None or not callable(handler):
                raise AttributeError(f"{type(self).__name__} 缺少工具处理函数 {handler_name}")
            self._handlers[spec.name] = handler

    def get_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return json.dumps(
                {
                    "error": f"未知工具: {name}",
                    "suggestion": "请使用 list_strategies 或 get_watchlist 查看可用功能",
                },
                ensure_ascii=False,
            )
        try:
            return handler(**arguments)
        except TypeError as ex:
            return json.dumps(
                {
                    "error": f"参数错误: {ex}",
                    "suggestion": "请检查工具参数格式，或尝试不带参数调用此工具",
                },
                ensure_ascii=False,
            )
        except RuntimeError as ex:
            return json.dumps(
                {
                    "error": str(ex),
                    "suggestion": "所需服务未就绪，请确认终端已完全启动",
                },
                ensure_ascii=False,
            )
        except Exception as ex:
            return json.dumps({"error": str(ex)}, ensure_ascii=False)
