"""MCP JSON 配置加载（``mcpServers`` 标准格式）。

配置优先级（后者覆盖同名 Provider）：

1. 项目根 ``mcp.json``（legacy）
2. ``mcp/mcp.json``（推荐：单文件多个 ``mcpServers``）
3. ``mcp/<name>.json``（可选：单服务补充/覆盖）
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

from pydantic import Field, ValidationError, field_validator

from vnpy_common.paths import PROJECT_ROOT
from vnpy_mcp.config.base import FrozenConfigModel
from vnpy_mcp.config.registry import BUILTIN_MCP_PROVIDERS

DEFAULT_MCP_DIR = PROJECT_ROOT / "mcp"
DEFAULT_TDX_MCP_URL = "https://mcp.tdx.com.cn:3001/mcp"
MCP_CONFIG_FILENAME = "mcp.json"

ROOT_MCP_CONFIG = PROJECT_ROOT / MCP_CONFIG_FILENAME
MCP_DIR_CONFIG = DEFAULT_MCP_DIR / MCP_CONFIG_FILENAME

_LEGACY_MCP_CONFIG_CANDIDATES = (ROOT_MCP_CONFIG,)

_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "your_api_key",
        "your-api-key",
        "YOUR_API_KEY",
        "您的API密钥",
        "您的 API 密钥",
    }
)


class McpServerConfig(FrozenConfigModel):
    name: str
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    title: str = ""
    description: str = ""
    source_path: str = ""

    @field_validator("name", "title", "description", "source_path", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("url", mode="before")
    @classmethod
    def _coerce_url(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("enabled", mode="before")
    @classmethod
    def _coerce_enabled(cls, value: Any) -> bool:
        return value if isinstance(value, bool) else True

    @field_validator("headers", mode="before")
    @classmethod
    def _coerce_headers(cls, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        return {str(key): str(val) for key, val in value.items()}

    @property
    def display_title(self) -> str:
        if self.title:
            return self.title
        meta = BUILTIN_MCP_PROVIDERS.get(self.name)
        if meta:
            return meta.title
        return self.name

    @property
    def display_description(self) -> str:
        if self.description:
            return self.description
        meta = BUILTIN_MCP_PROVIDERS.get(self.name)
        if meta:
            return meta.summary
        return f"远端 MCP：{self.name}"

    @property
    def config_hint(self) -> str:
        if self.source_path:
            return self.source_path
        return MCP_DIR_CONFIG.as_posix()

    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        if not self.url.strip():
            return False
        if not self.headers:
            return True
        return any(_is_valid_secret(value) for value in self.headers.values())

    @property
    def missing_hints(self) -> tuple[str, ...]:
        if self.available:
            return ()
        if not self.enabled:
            return (f"{self.config_hint}（enabled=false）",)
        if not self.url.strip():
            example = f"mcp/{MCP_CONFIG_FILENAME}.example"
            return (f"{self.config_hint} → mcpServers.{self.name}.url（可复制 {example}）",)
        if self.headers:
            return (f"{self.config_hint} → mcpServers.{self.name}.headers",)
        return (self.config_hint,)


def _is_valid_secret(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text in _PLACEHOLDER_KEYS:
        return False
    if text.startswith("您的"):
        return False
    return True


def resolve_mcp_dir() -> Path:
    override = os.getenv("MCP_DIR", "").strip()
    if override:
        return cast(Path, Path(override).expanduser())
    return DEFAULT_MCP_DIR


def resolve_mcp_config_paths() -> list[Path]:
    """按加载顺序返回存在的 MCP 配置文件。"""
    override = os.getenv("MCP_CONFIG_PATH", "").strip()
    if override:
        path = Path(override).expanduser()
        return [path] if path.is_file() else []

    paths: list[Path] = []
    for path in _LEGACY_MCP_CONFIG_CANDIDATES:
        if path.is_file():
            paths.append(path)

    mcp_dir = resolve_mcp_dir()
    dir_config = mcp_dir / MCP_CONFIG_FILENAME
    if dir_config.is_file():
        paths.append(dir_config)
    return paths


def _source_label(path: Path) -> str:
    try:
        rel = path.relative_to(PROJECT_ROOT)
        return rel.as_posix()
    except ValueError:
        return str(path)


def _parse_server_entry(
    name: str,
    entry: dict[str, Any],
    *,
    source_path: str = "",
) -> McpServerConfig | None:
    try:
        return McpServerConfig.model_validate(
            {
                **entry,
                "name": entry.get("name") or name,
                "source_path": source_path,
            }
        )
    except ValidationError:
        return None


def _load_mcp_servers_file(path: Path) -> dict[str, McpServerConfig]:
    """加载 MCP 标准格式：``{ "mcpServers": { ... } }``。"""
    if not path.is_file():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(raw, dict):
        return {}

    servers = raw.get("mcpServers")
    if not isinstance(servers, dict):
        return {}

    source_path = _source_label(path)
    result: dict[str, McpServerConfig] = {}
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            continue
        config = _parse_server_entry(str(name), entry, source_path=source_path)
        if config is not None:
            result[str(name)] = config
    return result


def _load_single_server_file(path: Path, *, mcp_dir: Path) -> McpServerConfig | None:
    """加载 ``mcp/<name>.json`` 单服务扩展格式。"""
    if not path.is_file():
        return None
    if path.name in (MCP_CONFIG_FILENAME, f"{MCP_CONFIG_FILENAME}.example"):
        return None
    if path.name.endswith(".example.json") or path.name.startswith("_"):
        return None
    if path.suffix.lower() != ".json":
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(raw, dict):
        return None

    try:
        rel = path.relative_to(mcp_dir)
        source_path = f"mcp/{rel.as_posix()}"
    except ValueError:
        source_path = _source_label(path)

    if "url" in raw or "headers" in raw or "enabled" in raw:
        return _parse_server_entry(path.stem, raw, source_path=source_path)

    servers = raw.get("mcpServers")
    if isinstance(servers, dict) and len(servers) == 1:
        name, entry = next(iter(servers.items()))
        if isinstance(entry, dict):
            return _parse_server_entry(str(name), entry, source_path=source_path)

    return None


def load_mcp_dir(path: Path | None = None) -> dict[str, McpServerConfig]:
    """加载 ``mcp/mcp.json``（多服务）及 ``mcp/*.json``（单服务扩展）。"""
    mcp_dir = path or resolve_mcp_dir()
    if not mcp_dir.is_dir():
        return {}

    result: dict[str, McpServerConfig] = {}
    result.update(_load_mcp_servers_file(mcp_dir / MCP_CONFIG_FILENAME))

    for filepath in sorted(mcp_dir.glob("*.json")):
        config = _load_single_server_file(filepath, mcp_dir=mcp_dir)
        if config is not None:
            result[config.name] = config
    return result


def load_all_mcp_servers(
    *,
    mcp_dir: Path | None = None,
    extra_paths: list[Path] | None = None,
) -> dict[str, McpServerConfig]:
    """合并所有 MCP 配置源。"""
    result: dict[str, McpServerConfig] = {}

    if extra_paths is not None:
        paths = extra_paths
    else:
        paths = resolve_mcp_config_paths()
        mcp_dir_path = mcp_dir or resolve_mcp_dir()
        dir_config = mcp_dir_path / MCP_CONFIG_FILENAME
        if dir_config.is_file() and dir_config not in paths:
            paths.append(dir_config)

    for config_path in paths:
        result.update(_load_mcp_servers_file(config_path))

    result.update(load_mcp_dir(mcp_dir))

    for name in BUILTIN_MCP_PROVIDERS:
        result.setdefault(
            name,
            McpServerConfig(
                name=name,
                source_path=MCP_DIR_CONFIG.as_posix(),
            ),
        )
    return result


def get_mcp_server(name: str) -> McpServerConfig | None:
    return load_all_mcp_servers().get(name)


def list_mcp_server_names() -> list[str]:
    return sorted(load_all_mcp_servers().keys())
