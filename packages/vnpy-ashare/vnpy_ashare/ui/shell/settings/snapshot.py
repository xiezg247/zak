"""配置页数据快照（.env + vt_setting）。"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field

from vnpy_ashare.config.bridge import (
    database_settings_from_env,
    load_effective_env_values,
    parse_env_file,
)
from vnpy_ashare.config.schema import (
    ENV_CONFIG_SPECS,
    ENV_DB_KEYS,
    ENV_POSTGRES_KEYS,
    ENV_SPECS_BY_GROUP,
    VT_CONFIG_SPECS,
    VT_DB_SPECS,
    VT_SPECS_BY_GROUP,
    ConfigFieldSpec,
    ConfigSource,
    normalize_database_name,
)
from vnpy_ashare.config.vt_settings import build_vt_settings, default_vt_settings, load_runtime_settings
from vnpy_common.domain.base import FrozenModel
from vnpy_common.paths import ENV_FILE, VNTRADER_DIR
from vnpy_common.storage.config import resolve_database_url


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


class MetadataStorageEntry(FrozenModel):
    """PostgreSQL 元数据连接说明。"""

    key: str = Field(description="键名")
    relative: str = Field(description="相对路径")
    path: Path = Field(description="绝对路径")
    description: str = Field(description="用途说明")


def mask_database_url(url: str) -> str:
    text = url.strip()
    if not text:
        return "未配置"
    if "@" in text:
        prefix, _, host_part = text.partition("@")
        if "://" in prefix:
            scheme, _, creds = prefix.partition("://")
            user = creds.split(":", 1)[0] if creds else ""
            return f"{scheme}://{user or '***'}@{host_part}"
    return text


def metadata_storage_entries(
    settings: dict | None = None,
) -> tuple[MetadataStorageEntry, ...]:
    _ = settings
    url = mask_database_url(resolve_database_url() or "")
    return (
        MetadataStorageEntry(
            key="DATABASE_URL",
            relative="",
            path=VNTRADER_DIR,
            description=f"PostgreSQL 元数据与对话（schema app / chat / auth / cache）：{url}",
        ),
    )


def format_meta_storage_root() -> str:
    return "PostgreSQL（.env 中 DATABASE_URL / POSTGRES_*）"


VT_DATABASE_KEYS: tuple[str, ...] = tuple(spec.key for spec in VT_DB_SPECS)


def resolve_database_runtime_display(
    runtime_settings: dict,
    *,
    toggle_mode: str | None = None,
    env_file: Path = ENV_FILE,
) -> dict[str, object]:
    """返回 K 线 PostgreSQL 运行时字段（合并 vt_setting 与 .env 预期值）。"""
    _ = toggle_mode
    env = load_effective_env_values(env_file)
    expected = database_settings_from_env(env)
    merged = dict(expected)
    for key in VT_DATABASE_KEYS:
        if key in runtime_settings:
            merged[key] = runtime_settings[key]
    merged["database.name"] = "postgresql"
    return merged


def collect_database_runtime_updates(
    widget_values: dict[str, object],
    *,
    toggle_mode: str | None = None,
    env_file: Path = ENV_FILE,
) -> dict[str, object]:
    """合并表单值为完整的 database.* 块。"""
    _ = toggle_mode
    env = load_effective_env_values(env_file)
    merged = database_settings_from_env(env)
    merged.update(widget_values)
    merged["database.name"] = "postgresql"
    return merged


class ResolvedConfigItem(FrozenModel):
    spec: ConfigFieldSpec = Field(description="配置项元数据")
    value: str = Field(description="当前生效值")
    default: str = Field(description="默认值")
    source: ConfigSource = Field(description="数据来源")
    file_value: str = Field(default="", description="配置文件中的原始值")


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
    return [item for item in resolve_env_config(env_file) if item.spec.key not in ENV_DB_KEYS]


def resolve_env_config_kline(env_file: Path = ENV_FILE) -> list[ResolvedConfigItem]:
    """K 线相关 .env 配置项（PostgreSQL）。"""
    file_values = parse_env_file(env_file)
    items: list[ResolvedConfigItem] = []
    for spec in ENV_CONFIG_SPECS:
        if spec.key == "DATABASE_NAME":
            env_value = file_values.get("DATABASE_NAME", spec.default)
            source: ConfigSource = "env" if "DATABASE_NAME" in file_values else "default"
            items.append(
                ResolvedConfigItem(
                    spec=spec,
                    value=normalize_database_name(env_value),
                    default=spec.default,
                    source=source,
                )
            )
            continue
        if spec.key not in ENV_POSTGRES_KEYS:
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
    """K 线库类型（恒为 postgresql）。"""
    _ = env_file
    return "postgresql"


def detect_database_mode(
    env_file: Path = ENV_FILE,
    *,
    runtime_settings: dict | None = None,
) -> str:
    """当前运行时 K 线库类型（恒为 postgresql）。"""
    _ = env_file
    if runtime_settings is not None:
        return normalize_database_name(str(runtime_settings.get("database.name", "postgresql")))
    return "postgresql"


def format_bar_database_status(
    *,
    effective: str,
    env_name: str,
    pending: str | None = None,
) -> str:
    """K 线存储状态摘要：运行时 / .env / 表单未保存。"""
    effective = normalize_database_name(effective)
    env_name = normalize_database_name(env_name)
    parts = [f"运行时 (vt_setting.json)：{effective}"]
    if env_name != effective:
        parts.append(f".env：{env_name}（未同步，请点「从 .env 同步」或保存下方运行时配置）")
    else:
        parts.append(f".env：{env_name}")
    if pending is not None:
        pending = normalize_database_name(pending)
        if pending != effective:
            parts.append(f"未保存：{pending}")
    return " · ".join(parts)


def resolve_env_config_by_group(
    env_file: Path = ENV_FILE,
) -> dict[str, list[ResolvedConfigItem]]:
    file_values = parse_env_file(env_file)
    grouped: dict[str, list[ResolvedConfigItem]] = {group: [] for group in ENV_SPECS_BY_GROUP}
    for spec in ENV_CONFIG_SPECS:
        if spec.key in file_values:
            value = file_values[spec.key]
            source: ConfigSource = "env"
        else:
            value = spec.default
            source = "default"
        grouped[spec.group].append(ResolvedConfigItem(spec=spec, value=value, default=spec.default, source=source))
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
