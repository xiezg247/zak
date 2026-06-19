"""AI 工具能力状态（Skills + MCP 统一视图）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, cast

from pydantic import Field

from skills.registry import OFFICIAL_SKILLS
from vnpy_common.domain.base import FrozenModel
from vnpy_mcp.app.engine import McpEngine
from vnpy_skills.app.engine import SkillEngine

ToolProviderState = Literal["ready", "missing_env", "connect_failed", "disabled", "idle"]


class ToolProviderStatus(FrozenModel):
    """单个 Skill 或 MCP 提供者状态。"""

    kind: Literal["skill", "mcp"] = Field(description="提供者类型")
    name: str = Field(description="内部名称")
    title: str = Field(description="展示标题")
    state: ToolProviderState = Field(description="就绪状态")
    tool_count: int = Field(description="可用工具数")
    missing_env: tuple[str, ...] = Field(default_factory=tuple, description="缺失环境变量")
    error: str = Field(default="", description="连接错误摘要")
    summary: str = Field(default="", description="能力摘要")


class ToolsStatusSnapshot(FrozenModel):
    """Skills + MCP 工具能力快照（AI 工具对话框展示）。"""

    skills: tuple[ToolProviderStatus, ...] = Field(default_factory=tuple, description="Skill 状态列表")
    mcps: tuple[ToolProviderStatus, ...] = Field(default_factory=tuple, description="MCP 状态列表")
    total_tools: int = Field(default=0, description="可用工具总数")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="快照时间")

    @property
    def ready_skill_count(self) -> int:
        return sum(1 for item in self.skills if item.state == "ready")

    @property
    def ready_mcp_count(self) -> int:
        return sum(1 for item in self.mcps if item.state == "ready")

    def compact_summary(self) -> str:
        """一行摘要：就绪 Skills / MCP 与待配置项数。"""
        parts: list[str] = []
        ready_skills = [s.title for s in self.skills if s.state == "ready"]
        if ready_skills:
            parts.append("Skills: " + " · ".join(ready_skills[:4]))
            if len(ready_skills) > 4:
                parts[-1] += f" 等 {len(ready_skills)} 个"
        ready_mcps = [m.title for m in self.mcps if m.state == "ready"]
        if ready_mcps:
            parts.append("MCP: " + " · ".join(ready_mcps))
        issues = [s for s in self.skills if s.state != "ready"] + [m for m in self.mcps if m.state not in ("ready", "idle")]
        if issues and not parts:
            parts.append(f"{len(issues)} 项待配置")
        elif issues:
            parts.append(f"{len(issues)} 项待配置")
        return "  |  ".join(parts) if parts else "暂无可用工具"


def _skill_title(name: str, fallback: str = "") -> str:
    meta = OFFICIAL_SKILLS.get(name)
    if meta:
        return cast(str, meta.title)
    return fallback or name


def _skill_summary(name: str, description: str = "") -> str:
    meta = OFFICIAL_SKILLS.get(name)
    if meta:
        return cast(str, meta.summary)
    return description


def _agent_skill_state(skill) -> ToolProviderState:
    missing = skill.missing_env
    if missing:
        return "missing_env"
    return "ready"


def build_tools_status(
    skill_engine: SkillEngine,
    mcp_engine: McpEngine,
) -> ToolsStatusSnapshot:
    """聚合 SkillEngine 与 McpEngine 状态，供 AI 面板工具能力 UI 使用。"""
    skills: list[ToolProviderStatus] = []
    enabled_agent = {s.name for s in skill_engine.get_enabled_agent_skills()}

    for name, skill in sorted(skill_engine.agent_skills.items()):
        if name not in enabled_agent:
            continue
        state = _agent_skill_state(skill)
        skills.append(
            ToolProviderStatus(
                kind="skill",
                name=name,
                title=_skill_title(name, name),
                state=state,
                tool_count=0,
                missing_env=tuple(skill.missing_env),
                summary=_skill_summary(name, skill.description) + "（通过 read_skill_file / run_python 调用）",
            )
        )

    for key, instance in sorted(skill_engine.instances.items()):
        skills.append(
            ToolProviderStatus(
                kind="skill",
                name=key,
                title=_skill_title(key, key),
                state="ready",
                tool_count=len(instance.get_tools()),
                summary=_skill_summary(key, instance.description),
            )
        )

    loaded_python = set(skill_engine.instances.keys())
    for class_name, cls in sorted(skill_engine.classes.items()):
        key = cls().skill_name or class_name
        if key in loaded_python:
            continue
        probe = cls()
        probe.on_init()
        if probe.available:
            continue
        skills.append(
            ToolProviderStatus(
                kind="skill",
                name=key,
                title=_skill_title(key, key),
                state="disabled",
                tool_count=0,
                summary=probe.description or "未启用",
            )
        )

    mcps: list[ToolProviderStatus] = []
    connect_errors = mcp_engine.get_connect_errors()

    for name, provider in sorted(mcp_engine.providers.items()):
        provider_config = getattr(provider, "config", None)
        if provider_config is None:
            continue
        title = provider_config.display_title
        summary = provider_config.display_description

        if not provider.available:
            missing = getattr(provider, "missing_env", [])
            remote = getattr(provider, "enabled", True)
            mcp_state: ToolProviderState = "disabled" if remote is False else "missing_env"
            mcps.append(
                ToolProviderStatus(
                    kind="mcp",
                    name=name,
                    title=title,
                    state=mcp_state,
                    tool_count=0,
                    missing_env=tuple(missing),
                    summary=summary,
                )
            )
            continue

        if not mcp_engine.providers_initialized:
            mcps.append(
                ToolProviderStatus(
                    kind="mcp",
                    name=name,
                    title=title,
                    state="idle",
                    tool_count=0,
                    summary=f"{summary}（首次使用时连接）",
                )
            )
            continue

        if provider.connected:
            mcps.append(
                ToolProviderStatus(
                    kind="mcp",
                    name=name,
                    title=title,
                    state="ready",
                    tool_count=len(provider.tools),
                    summary=summary,
                )
            )
            continue

        error = connect_errors.get(name, "连接失败")
        mcps.append(
            ToolProviderStatus(
                kind="mcp",
                name=name,
                title=title,
                state="connect_failed",
                tool_count=0,
                error=error[:500],
                summary=summary,
            )
        )

    total_tools = skill_engine.get_tool_specs()
    total = len(total_tools) + len(mcp_engine.get_tool_specs())

    return ToolsStatusSnapshot(
        skills=tuple(skills),
        mcps=tuple(mcps),
        total_tools=total,
    )
