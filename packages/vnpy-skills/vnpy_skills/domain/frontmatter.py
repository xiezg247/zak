"""SKILL.md frontmatter 解析与校验。"""

from __future__ import annotations

import json
import re
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillCredential(BaseModel):
    """SKILL.md credentials 条目。"""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    how_to_get: str = ""


class SkillEnvVar(BaseModel):
    """requirements.environment_variables 条目。"""

    model_config = ConfigDict(extra="allow")

    name: str
    required: bool = False
    sensitive: bool = False


class SkillRequirements(BaseModel):
    """SKILL.md requirements 块。"""

    model_config = ConfigDict(extra="allow")

    python: str = ""
    environment_variables: list[SkillEnvVar] = Field(default_factory=list)
    network_access: bool = False


class SkillFrontmatter(BaseModel):
    """SKILL.md YAML frontmatter。"""

    model_config = ConfigDict(extra="allow")

    name: str = ""
    description: str = ""
    author: str = ""
    version: str = ""
    homepage: str = ""
    credentials: list[SkillCredential] = Field(default_factory=list)
    requirements: SkillRequirements | None = None
    metadata: Any = None

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> SkillFrontmatter:
        data = dict(raw)
        metadata = data.get("metadata")
        if isinstance(metadata, str):
            try:
                data["metadata"] = json.loads(metadata)
            except json.JSONDecodeError:
                pass
        return cls.model_validate(data)

    def env_requirements(self) -> list[tuple[str, bool]]:
        """解析所需环境变量：(变量名, 是否严格缺失即告警)。"""
        required: list[tuple[str, bool]] = []

        for cred in self.credentials:
            if cred.name:
                required.append((cred.name, True))

        if self.requirements is not None:
            for env in self.requirements.environment_variables:
                if env.name:
                    required.append((env.name, env.required))

        for env_name in _extract_env_from_metadata(self.metadata):
            required.append((env_name, False))

        if any(name == "TUSHARE_TOKEN" for name, _ in required):
            pass
        elif "TUSHARE_TOKEN" in json.dumps(self.model_dump(mode="json"), ensure_ascii=False):
            required.append(("TUSHARE_TOKEN", False))

        seen: set[str] = set()
        unique: list[tuple[str, bool]] = []
        for name, strict in required:
            if name not in seen:
                seen.add(name)
                unique.append((name, strict))
        return unique


def _extract_env_from_metadata(metadata: Any) -> list[str]:
    if isinstance(metadata, str):
        key_names = re.findall(r'"([A-Z_]+)"', metadata)
        return [name for name in key_names if name.endswith("_KEY") or name.endswith("_TOKEN")]

    if not isinstance(metadata, dict):
        return []

    names: list[str] = []
    claw = metadata.get("clawdbot")
    if isinstance(claw, dict):
        requires = claw.get("requires")
        if isinstance(requires, dict):
            env = requires.get("env")
            if isinstance(env, list):
                names.extend(str(item) for item in env if item)
    return names


def _parse_frontmatter_fallback(raw: str) -> dict[str, Any]:
    """YAML 解析失败时的逐行 key:value 回退。"""
    meta: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def parse_skill_document(text: str) -> tuple[SkillFrontmatter, str]:
    """从 SKILL.md 全文解析 frontmatter 与正文。"""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return SkillFrontmatter(), text.strip()

    raw_yaml = match.group(1)
    body = text[match.end() :].strip()
    try:
        loaded = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        loaded = _parse_frontmatter_fallback(raw_yaml)

    if not isinstance(loaded, dict):
        loaded = {}
    return SkillFrontmatter.from_raw(loaded), body
