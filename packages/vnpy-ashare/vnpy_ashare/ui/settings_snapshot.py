"""配置页数据快照（.env + vt_setting）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from vnpy_ashare.config_bridge import (
    database_settings_from_env,
    load_effective_env_values,
    parse_env_file,
)
from vnpy_ashare.config_schema import (
    ENV_CONFIG_SPECS,
    ENV_DB_KEYS,
    ENV_POSTGRES_KEYS,
    ENV_SPECS_BY_GROUP,
    VT_CONFIG_SPECS,
    VT_DB_SPECS,
    VT_META_DB_SPECS,
    VT_SPECS_BY_GROUP,
    ConfigFieldSpec,
    ConfigSource,
    normalize_database_name,
)
from vnpy_common.paths import ENV_FILE, VNTRADER_DIR, get_app_db_path, get_chat_db_path, meta_db_filenames
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


@dataclass(frozen=True)
class MetadataStorageEntry:
    """固定 SQLite 元数据文件（不受 DATABASE_NAME 影响）。"""

    key: str
    relative: str
    path: Path
    description: str


def metadata_storage_entries(
    settings: dict | None = None,
) -> tuple[MetadataStorageEntry, ...]:
    runtime = settings or load_runtime_settings()
    app_relative, chat_relative = meta_db_filenames(runtime)
    descriptions = {spec.key: spec.description for spec in VT_META_DB_SPECS}
    return (
        MetadataStorageEntry(
            key="database.meta.app",
            relative=app_relative,
            path=get_app_db_path(runtime),
            description=descriptions.get("database.meta.app", "业务元数据"),
        ),
        MetadataStorageEntry(
            key="database.meta.chat",
            relative=chat_relative,
            path=get_chat_db_path(runtime),
            description=descriptions.get("database.meta.chat", "AI 对话"),
        ),
    )


def format_meta_storage_root() -> str:
    return f"{VNTRADER_DIR}（vt_setting.json 中路径均相对此目录）"


VT_DATABASE_KEYS: tuple[str, ...] = tuple(spec.key for spec in VT_DB_SPECS)


def normalize_sqlite_database_file(value: str) -> str:
    """修正 SQLite 模式下误写入的 PG 库名等非文件路径。"""
    text = value.strip()
    if not text:
        return "database.db"
    if text.endswith(".db") or "/" in text or "\\" in text:
        return text
    return "database.db"


def resolve_database_runtime_display(
    runtime_settings: dict,
    *,
    toggle_mode: str,
    env_file: Path = ENV_FILE,
) -> dict[str, object]:
    """按 K 线切换模式返回应展示的运行时字段，避免 PG/SQLite 字段串值。"""
    toggle_mode = normalize_database_name(toggle_mode)
    env = load_effective_env_values(env_file)
    env_mode = normalize_database_name(env.get("DATABASE_NAME", "sqlite"))
    runtime_mode = normalize_database_name(str(runtime_settings.get("database.name", "sqlite")))

    env_for_toggle = dict(env)
    env_for_toggle["DATABASE_NAME"] = toggle_mode
    expected = database_settings_from_env(env_for_toggle)

    if toggle_mode == runtime_mode == env_mode:
        merged = dict(expected)
        for key in VT_DATABASE_KEYS:
            if key in runtime_settings:
                merged[key] = runtime_settings[key]
        if toggle_mode == "sqlite":
            merged["database.database"] = normalize_sqlite_database_file(str(merged.get("database.database", "database.db")))
        return merged

    return expected


def collect_database_runtime_updates(
    widget_values: dict[str, object],
    *,
    toggle_mode: str,
    env_file: Path = ENV_FILE,
) -> dict[str, object]:
    """合并表单值为完整的 database.* 块（按模式清空无关字段）。"""
    toggle_mode = normalize_database_name(toggle_mode)
    env = load_effective_env_values(env_file)
    env["DATABASE_NAME"] = toggle_mode
    merged = database_settings_from_env(env)
    merged.update(widget_values)
    merged["database.name"] = toggle_mode
    if toggle_mode == "sqlite":
        merged["database.database"] = normalize_sqlite_database_file(str(merged.get("database.database", "database.db")))
    return merged


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
    return [item for item in resolve_env_config(env_file) if item.spec.key not in ENV_DB_KEYS]


def resolve_env_config_kline(env_file: Path = ENV_FILE) -> list[ResolvedConfigItem]:
    """K 线相关 .env 配置项（只读，始终按 .env 中 DATABASE_NAME 过滤）。"""
    mode = env_database_name(env_file)
    file_values = parse_env_file(env_file)
    items: list[ResolvedConfigItem] = []
    for spec in ENV_CONFIG_SPECS:
        if spec.key == "DATABASE_NAME":
            env_value = file_values.get("DATABASE_NAME", spec.default)
            env_name = normalize_database_name(env_value)
            source: ConfigSource = "env" if "DATABASE_NAME" in file_values else "default"
            items.append(
                ResolvedConfigItem(
                    spec=spec,
                    value=env_name,
                    default=spec.default,
                    source=source,
                )
            )
            continue
        if mode != "postgresql" or spec.key not in ENV_POSTGRES_KEYS:
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


def resolve_env_config_database(
    database: str,
    env_file: Path = ENV_FILE,
) -> list[ResolvedConfigItem]:
    """兼容旧调用；K 线 .env 展示与 ``database`` 参数无关，始终读 .env。"""
    _ = database
    return resolve_env_config_kline(env_file)


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


def format_database_status(
    *,
    effective: str,
    env_name: str,
    editing: str | None = None,
    pending: str | None = None,
) -> str:
    """兼容旧名；``editing`` 为 ``pending`` 别名。"""
    return format_bar_database_status(
        effective=effective,
        env_name=env_name,
        pending=pending if pending is not None else editing,
    )


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
