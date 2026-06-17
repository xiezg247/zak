"""Agent Skill 加载（SKILL.md 格式，兼容 Cursor / Claude Code 生态）。"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field

from vnpy_common.domain.base import MutableModel
from vnpy_skills.domain.frontmatter import SkillFrontmatter, parse_skill_document


class AgentSkill(MutableModel):
    """官方 / 第三方 SKILL.md 技能包。"""

    name: str = Field(description="技能名称")
    root: Path = Field(description="技能根目录")
    description: str = Field(default="", description="技能说明")
    author: str = Field(default="", description="作者")
    version: str = Field(default="", description="版本号")
    skill_md: str = Field(default="", description="SKILL.md 全文")
    body: str = Field(default="", description="SKILL.md 正文")
    frontmatter: SkillFrontmatter = Field(default_factory=SkillFrontmatter, description="YAML frontmatter")
    env_requirements: list[tuple[str, bool]] = Field(default_factory=list, description="所需环境变量")

    @classmethod
    def from_directory(cls, root: Path) -> AgentSkill | None:
        skill_file = root / "SKILL.md"
        if not skill_file.is_file():
            return None

        text = skill_file.read_text(encoding="utf-8")
        frontmatter, body = parse_skill_document(text)
        name = frontmatter.name or root.name

        return cls(
            name=name,
            root=root.resolve(),
            description=frontmatter.description,
            author=frontmatter.author,
            version=frontmatter.version,
            skill_md=text,
            body=body,
            frontmatter=frontmatter,
            env_requirements=frontmatter.env_requirements(),
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
            lines.append(f"（缺少环境变量: {', '.join(self.missing_env)}，部分功能可能受限）")
        lines.append(f'详细 API 与示例请按需调用 read_skill_file(skill="{self.name}", path="SKILL.md") 或 references/ 下文档。')
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
