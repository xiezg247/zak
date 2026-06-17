"""项目可配置项定义（.env + vt_setting.json）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vnpy_ashare.config.fonts import default_font_family
from vnpy_llm.config import DEFAULT_BASE_URL, DEFAULT_MODEL

ValueKind = Literal["text", "secret", "bool", "int", "choice"]
ConfigSource = Literal["env", "default", "vt_file"]


@dataclass(frozen=True)
class ConfigFieldSpec:
    key: str
    label: str
    group: str
    default: str
    sensitive: bool = False
    kind: ValueKind = "text"
    choices: tuple[str, ...] = ()
    description: str = ""


ENV_CONFIG_SPECS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        "TICKFLOW_API_KEY",
        "TickFlow API Key",
        "数据源",
        "",
        sensitive=True,
        description="主行情数据源，https://tickflow.org",
    ),
    ConfigFieldSpec(
        "TUSHARE_TOKEN",
        "Tushare Token",
        "数据源",
        "",
        sensitive=True,
        description="财务/选股辅助，https://tushare.pro",
    ),
    ConfigFieldSpec(
        "DATAFEED_NAME",
        "默认行情数据源",
        "数据源",
        "tickflow",
        kind="choice",
        choices=("tickflow", "tushare"),
    ),
    ConfigFieldSpec(
        "DATABASE_NAME",
        "K 线数据库类型",
        "数据库",
        "sqlite",
        kind="choice",
        choices=("sqlite", "postgresql"),
    ),
    ConfigFieldSpec(
        "REDIS_URL",
        "Redis URL",
        "Redis 行情",
        "redis://127.0.0.1:6379/0",
        description="例：redis://127.0.0.1:6379/0 或 redis://:password@host:6379/0",
    ),
    ConfigFieldSpec(
        "QUOTE_COLLECT_INTERVAL",
        "行情采集间隔（秒）",
        "Redis 行情",
        "15",
        kind="int",
    ),
    ConfigFieldSpec(
        "LLM_API_BASE",
        "LLM API Base",
        "大模型",
        DEFAULT_BASE_URL,
    ),
    ConfigFieldSpec(
        "LLM_API_KEY",
        "LLM API Key",
        "大模型",
        "",
        sensitive=True,
    ),
    ConfigFieldSpec(
        "LLM_MODEL",
        "LLM Model",
        "大模型",
        DEFAULT_MODEL,
    ),
    ConfigFieldSpec("LLM_MAX_TOKENS", "LLM Max Tokens", "大模型", "4096", kind="int"),
    ConfigFieldSpec("LLM_TEMPERATURE", "LLM Temperature", "大模型", "0.7"),
    ConfigFieldSpec("POSTGRES_HOST", "PostgreSQL 主机", "PostgreSQL", "localhost"),
    ConfigFieldSpec("POSTGRES_PORT", "PostgreSQL 端口", "PostgreSQL", "5432", kind="int"),
    ConfigFieldSpec("POSTGRES_USER", "PostgreSQL 用户名", "PostgreSQL", "zak"),
    ConfigFieldSpec(
        "POSTGRES_PASSWORD",
        "PostgreSQL 密码",
        "PostgreSQL",
        "zak",
        sensitive=True,
    ),
    ConfigFieldSpec("POSTGRES_DATABASE", "PostgreSQL 库名", "PostgreSQL", "zak"),
    ConfigFieldSpec(
        "NOTIFY_ENABLED",
        "启用消息通知",
        "消息通知",
        "false",
        kind="bool",
        description="开启后按下方事件订阅向飞书 Webhook 推送",
    ),
    ConfigFieldSpec(
        "FEISHU_WEBHOOK_URL",
        "飞书 Webhook URL",
        "消息通知",
        "",
        sensitive=True,
        description="飞书群 → 设置 → 群机器人 → 添加自定义机器人",
    ),
    ConfigFieldSpec(
        "NOTIFY_MIN_INTERVAL_SEC",
        "通知最小间隔（秒）",
        "消息通知",
        "30",
        kind="int",
        description="两次出站之间的最短间隔，默认 30",
    ),
)

VT_CONFIG_SPECS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        "datafeed.name",
        "数据源",
        "数据服务",
        "tickflow",
        kind="choice",
        choices=("tickflow", "tushare"),
    ),
    ConfigFieldSpec("datafeed.username", "数据源用户名", "数据服务", "api_key"),
    ConfigFieldSpec(
        "datafeed.password",
        "API Key / Token",
        "数据服务",
        "",
        sensitive=True,
    ),
    ConfigFieldSpec(
        "database.name",
        "K 线数据库类型",
        "K 线",
        "sqlite",
        kind="choice",
        choices=("sqlite", "postgresql"),
    ),
    ConfigFieldSpec("database.host", "PostgreSQL 主机", "K 线", ""),
    ConfigFieldSpec("database.port", "PostgreSQL 端口", "K 线", "0", kind="int"),
    ConfigFieldSpec("database.user", "PostgreSQL 用户名", "K 线", ""),
    ConfigFieldSpec("database.password", "PostgreSQL 密码", "K 线", "", sensitive=True),
    ConfigFieldSpec("database.database", "K 线 SQLite 文件", "K 线", "database.db"),
    ConfigFieldSpec(
        "database.meta.app",
        "元数据 SQLite 文件",
        "元数据",
        "zak.db",
        description="相对 ~/.vntrader/；自选、universe、回测/选股历史",
    ),
    ConfigFieldSpec(
        "database.meta.chat",
        "AI 对话 SQLite 文件",
        "元数据",
        "llm_chat.db",
        description="相对 ~/.vntrader/；不受 database.name 影响",
    ),
    ConfigFieldSpec("font.family", "字体", "界面与日志", default_font_family()),
    ConfigFieldSpec("font.size", "字号", "界面与日志", "12", kind="int"),
    ConfigFieldSpec("log.active", "启用日志", "界面与日志", "true", kind="bool"),
    ConfigFieldSpec(
        "log.level",
        "日志级别",
        "界面与日志",
        "INFO",
        kind="choice",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    ),
)

ENV_SPECS_BY_GROUP: dict[str, tuple[ConfigFieldSpec, ...]] = {}
VT_SPECS_BY_GROUP: dict[str, tuple[ConfigFieldSpec, ...]] = {}


def _index_specs(
    specs: tuple[ConfigFieldSpec, ...],
) -> dict[str, tuple[ConfigFieldSpec, ...]]:
    groups: dict[str, list[ConfigFieldSpec]] = {}
    for spec in specs:
        groups.setdefault(spec.group, []).append(spec)
    return {name: tuple(items) for name, items in groups.items()}


ENV_SPECS_BY_GROUP = _index_specs(ENV_CONFIG_SPECS)
VT_SPECS_BY_GROUP = _index_specs(VT_CONFIG_SPECS)

ENV_POSTGRES_KEYS: frozenset[str] = frozenset(spec.key for spec in ENV_CONFIG_SPECS if spec.group == "PostgreSQL")
ENV_DB_KEYS: frozenset[str] = frozenset({"DATABASE_NAME"}) | ENV_POSTGRES_KEYS
ENV_NOTIFY_KEYS: frozenset[str] = frozenset(
    {"NOTIFY_ENABLED", "FEISHU_WEBHOOK_URL", "NOTIFY_MIN_INTERVAL_SEC"},
)

ENV_SPEC_BY_KEY: dict[str, ConfigFieldSpec] = {spec.key: spec for spec in ENV_CONFIG_SPECS}
ENV_GENERAL_SPECS: tuple[ConfigFieldSpec, ...] = tuple(
    spec for spec in ENV_CONFIG_SPECS if spec.key not in ENV_DB_KEYS and spec.key not in ENV_NOTIFY_KEYS
)
ENV_NOTIFY_SPECS: tuple[ConfigFieldSpec, ...] = tuple(spec for spec in ENV_CONFIG_SPECS if spec.key in ENV_NOTIFY_KEYS)

VT_META_DB_SPECS: tuple[ConfigFieldSpec, ...] = tuple(spec for spec in VT_CONFIG_SPECS if spec.key.startswith("database.meta."))
VT_DB_SPECS: tuple[ConfigFieldSpec, ...] = tuple(
    spec for spec in VT_CONFIG_SPECS if spec.key.startswith("database.") and not spec.key.startswith("database.meta.")
)
VT_NON_DB_SPECS: tuple[ConfigFieldSpec, ...] = tuple(spec for spec in VT_CONFIG_SPECS if not spec.key.startswith("database."))
VT_POSTGRES_KEYS: frozenset[str] = frozenset(spec.key for spec in VT_DB_SPECS if spec.key not in {"database.name", "database.database"})
VT_SQLITE_KEYS: frozenset[str] = frozenset({"database.name", "database.database"})


def normalize_database_name(name: str) -> str:
    text = name.strip().lower()
    return text if text in {"sqlite", "postgresql"} else "sqlite"
