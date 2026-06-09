"""Agent Skill 加载（SKILL.md 格式，兼容 Cursor / Claude Code 生态）。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text.strip()

    raw = match.group(1)
    body = text[match.end() :].strip()
    meta: dict[str, Any] = {}

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")

    return meta, body


def _parse_env_requirements(meta: dict[str, Any]) -> list[tuple[str, bool]]:
    """从 frontmatter 解析所需环境变量。"""
    required: list[tuple[str, bool]] = []

    credentials = meta.get("credentials")
    if isinstance(credentials, list):
        for item in credentials:
            if isinstance(item, dict) and item.get("name"):
                required.append((str(item["name"]), True))

    # tickflow metadata JSON
    metadata_raw = meta.get("metadata")
    if isinstance(metadata_raw, str) and "env" in metadata_raw:
        for name in re.findall(r'"([A-Z_]+)"', metadata_raw):
            if name.endswith("_KEY") or name.endswith("_TOKEN"):
                required.append((name, False))

    if "TUSHARE_TOKEN" in str(meta):
        required.append(("TUSHARE_TOKEN", False))

    # 去重
    seen: set[str] = set()
    unique: list[tuple[str, bool]] = []
    for name, strict in required:
        if name not in seen:
            seen.add(name)
            unique.append((name, strict))
    return unique


@dataclass
class AgentSkill:
    """官方 / 第三方 SKILL.md 技能包。"""

    name: str
    root: Path
    description: str = ""
    author: str = ""
    version: str = ""
    skill_md: str = ""
    body: str = ""
    frontmatter: dict[str, Any] = field(default_factory=dict)
    env_requirements: list[tuple[str, bool]] = field(default_factory=list)

    @classmethod
    def from_directory(cls, root: Path) -> AgentSkill | None:
        skill_file = root / "SKILL.md"
        if not skill_file.is_file():
            return None

        text = skill_file.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        name = str(meta.get("name") or root.name)

        return cls(
            name=name,
            root=root.resolve(),
            description=str(meta.get("description") or ""),
            author=str(meta.get("author") or ""),
            version=str(meta.get("version") or ""),
            skill_md=text,
            body=body,
            frontmatter=meta,
            env_requirements=_parse_env_requirements(meta),
        )

    @property
    def available(self) -> bool:
        """Agent Skill 始终加载；缺少 Token 时在 prompt 中提示。"""
        return True

    @property
    def missing_env(self) -> list[str]:
        missing: list[str] = []
        for env_name, strict in self.env_requirements:
            if strict and not os.getenv(env_name, "").strip():
                missing.append(env_name)
        return missing

    def resolve_path(self, rel_path: str) -> Path | None:
        """解析 skill 内相对路径，禁止目录穿越。"""
        rel = rel_path.strip().lstrip("/")
        if not rel or ".." in Path(rel).parts:
            return None
        target = (self.root / rel).resolve()
        if not str(target).startswith(str(self.root)):
            return None
        return target

    def read_file(self, rel_path: str, *, max_chars: int = 120_000) -> str:
        target = self.resolve_path(rel_path)
        if target is None:
            return f"错误：非法路径 {rel_path}"
        if not target.is_file():
            return f"错误：文件不存在 {rel_path}"
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + f"\n\n...(已截断，共 {len(text)} 字符)"
        return text

    def prompt_section(self) -> str:
        """注入 System Prompt 的 Skill 摘要（不含 SKILL.md 正文）。"""
        lines = [f"### Skill: {self.name}"]
        if self.description:
            lines.append(self.description)
        if self.missing_env:
            lines.append(
                f"（缺少环境变量: {', '.join(self.missing_env)}，部分功能可能受限）"
            )
        lines.append(
            "详细 API 与示例请按需调用 read_skill_file(skill="
            f'"{self.name}", path="SKILL.md") 或 references/ 下文档。'
        )
        return "\n".join(lines)

    def prompt_section_full(self) -> str:
        """完整 SKILL.md 正文（调试或显式按需加载时使用）。"""
        header = f"### Skill: {self.name}"
        if self.description:
            header += f"\n{self.description}"
        if self.missing_env:
            header += f"\n（缺少环境变量: {', '.join(self.missing_env)}，部分功能可能受限）"
        return f"{header}\n\n{self.body}"

    def list_files(self, subdir: str = "") -> list[str]:
        base = self.resolve_path(subdir) if subdir else self.root
        if base is None or not base.is_dir():
            return []
        files: list[str] = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                files.append(str(path.relative_to(self.root)))
        return files
