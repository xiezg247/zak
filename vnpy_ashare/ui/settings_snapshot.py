"""配置页数据快照（.env + vt_setting）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from vnpy_ashare.config_schema import (
    ENV_CONFIG_SPECS,
    ENV_DB_KEYS,
    ENV_QUESTDB_KEYS,
    ENV_SPECS_BY_GROUP,
    VT_CONFIG_SPECS,
    VT_SPECS_BY_GROUP,
    ConfigFieldSpec,
    ConfigSource,
    normalize_database_name,
)
from vnpy_ashare.paths import ENV_FILE
from vnpy_ashare.vt_settings import build_vt_settings, default_vt_settings, load_runtime_settings


def mask_secret(value: str) -> str:
    text = value.strip()
    if not text:
        return "未配置"
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}…{text[-4:]}"


def is_configured(value: str) -> bool:
    return bool(value.strip())


def format_config_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_env_file(path: Path) -> dict[str, str]:
    """解析 .env 文件中显式定义的键值。"""
    if not path.is_file():
        return {}

    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result


@dataclass(frozen=True)
class ResolvedConfigItem:
    spec: ConfigFieldSpec
    value: str
    default: str
    source: ConfigSource
    file_value: str = ""


def resolve_env_config(env_file: Path = ENV_FILE) -> list[ResolvedConfigItem]:
    """全部 .env 配置项：.env 有定义则用其值，否则用默认值。"""
    file_values = parse_env_file(env_file)
    items: list[ResolvedConfigItem] = []
    for spec in ENV_CONFIG_SPECS:
        if spec.key in file_values:
            value = file_values[spec.key]
            source: ConfigSource = "env"
        else:
            value = spec.default
            source = "default"
        items.append(
            ResolvedConfigItem(
                spec=spec,
                value=value,
                default=spec.default,
                source=source,
            )
        )
    return items


def resolve_env_config_general(env_file: Path = ENV_FILE) -> list[ResolvedConfigItem]:
    """非数据库相关的 .env 配置项。"""
    return [
        item for item in resolve_env_config(env_file) if item.spec.key not in ENV_DB_KEYS
    ]


def resolve_env_config_database(
    database: str,
    env_file: Path = ENV_FILE,
) -> list[ResolvedConfigItem]:
    """当前数据库类型对应的 .env 配置项（DATABASE_NAME 与所选模式一致）。"""
    mode = normalize_database_name(database)
    file_values = parse_env_file(env_file)
    items: list[ResolvedConfigItem] = []
    for spec in ENV_CONFIG_SPECS:
        if spec.key == "DATABASE_NAME":
            env_value = file_values.get("DATABASE_NAME", spec.default)
            source: ConfigSource = "env" if "DATABASE_NAME" in file_values else "default"
            items.append(
                ResolvedConfigItem(
                    spec=spec,
                    value=mode,
                    default=spec.default,
                    source=source,
                    file_value=normalize_database_name(env_value),
                )
            )
            continue
        if mode != "questdb" or spec.key not in ENV_QUESTDB_KEYS:
            continue
        if spec.key in file_values:
            value = file_values[spec.key]
            source = "env"
        else:
            value = spec.default
            source = "default"
        items.append(
            ResolvedConfigItem(
                spec=spec,
                value=value,
                default=spec.default,
                source=source,
            )
        )
    return items


def env_database_name(env_file: Path = ENV_FILE) -> str:
    """.env 中的 DATABASE_NAME（未定义则用默认值）。"""
    for item in resolve_env_config(env_file):
        if item.spec.key == "DATABASE_NAME":
            return normalize_database_name(item.value)
    return "sqlite"


def detect_database_mode(
    env_file: Path = ENV_FILE,
    *,
    runtime_settings: dict | None = None,
) -> str:
    """当前运行时生效的数据库类型（vt_setting.json 的 database.name）。"""
    if runtime_settings is None:
        runtime_settings = load_runtime_settings()
    return normalize_database_name(str(runtime_settings.get("database.name", "sqlite")))


def format_database_status(
    *,
    effective: str,
    env_name: str,
    editing: str | None = None,
) -> str:
    """数据库状态摘要：运行时 / .env / 未保存编辑。"""
    effective = normalize_database_name(effective)
    env_name = normalize_database_name(env_name)
    parts = [f"当前生效：{effective}"]
    if env_name != effective:
        parts.append(f".env：{env_name}")
    if editing is not None:
        editing = normalize_database_name(editing)
        if editing != effective:
            parts.append(f"未保存：{editing}")
    return " · ".join(parts)


def resolve_env_config_by_group(
    env_file: Path = ENV_FILE,
) -> dict[str, list[ResolvedConfigItem]]:
    file_values = parse_env_file(env_file)
    grouped: dict[str, list[ResolvedConfigItem]] = {
        group: [] for group in ENV_SPECS_BY_GROUP
    }
    for spec in ENV_CONFIG_SPECS:
        if spec.key in file_values:
            value = file_values[spec.key]
            source: ConfigSource = "env"
        else:
            value = spec.default
            source = "default"
        grouped[spec.group].append(
            ResolvedConfigItem(spec=spec, value=value, default=spec.default, source=source)
        )
    return grouped


def _vt_source(
    key: str,
    *,
    current: dict,
    defaults: dict,
    from_env: dict,
) -> ConfigSource:
    current_text = format_config_value(current.get(key, defaults.get(key, "")))
    default_text = format_config_value(defaults.get(key, ""))
    env_text = format_config_value(from_env.get(key, defaults.get(key, "")))

    if current_text == default_text:
        return "default"
    if current_text == env_text and current_text != default_text:
        return "env"
    return "vt_file"


def resolve_vt_config() -> list[ResolvedConfigItem]:
    """全部 vt_setting 配置项：当前运行时值 + 来源标记。"""
    load_dotenv(ENV_FILE, override=True)
    defaults = default_vt_settings()
    from_env = build_vt_settings()
    current = load_runtime_settings()

    items: list[ResolvedConfigItem] = []
    for spec in VT_CONFIG_SPECS:
        raw = current.get(spec.key, from_env.get(spec.key, defaults.get(spec.key, spec.default)))
        value = format_config_value(raw)
        default = format_config_value(defaults.get(spec.key, spec.default))
        source = _vt_source(
            spec.key,
            current=current,
            defaults=defaults,
            from_env=from_env,
        )
        items.append(
            ResolvedConfigItem(
                spec=spec,
                value=value,
                default=default,
                source=source,
            )
        )
    return items


def resolve_vt_config_by_group() -> dict[str, list[ResolvedConfigItem]]:
    grouped: dict[str, list[ResolvedConfigItem]] = {group: [] for group in VT_SPECS_BY_GROUP}
    for item in resolve_vt_config():
        grouped[item.spec.group].append(item)
    return grouped


def editable_setting_keys() -> tuple[str, ...]:
    return tuple(spec.key for spec in VT_CONFIG_SPECS)


def collect_editable_values(settings: dict | None = None) -> dict:
    source = settings or load_runtime_settings()
    return {key: source.get(key) for key in editable_setting_keys() if key in source}
