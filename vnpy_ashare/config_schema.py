"""项目可配置项定义（.env + vt_setting.json）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vnpy_llm.config import DEFAULT_BASE_URL, DEFAULT_MODEL

from vnpy_ashare.ui.fonts import default_font_family

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
        choices=("sqlite", "questdb"),
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
    ConfigFieldSpec("QUESTDB_HOST", "QuestDB 主机", "QuestDB", "localhost"),
    ConfigFieldSpec("QUESTDB_PORT", "QuestDB 端口", "QuestDB", "8812", kind="int"),
    ConfigFieldSpec("QUESTDB_HTTP_PORT", "QuestDB HTTP 端口", "QuestDB", "9000", kind="int"),
    ConfigFieldSpec("QUESTDB_USER", "QuestDB 用户名", "QuestDB", "admin"),
    ConfigFieldSpec(
        "QUESTDB_PASSWORD",
        "QuestDB 密码",
        "QuestDB",
        "quest",
        sensitive=True,
    ),
    ConfigFieldSpec("QUESTDB_DATABASE", "QuestDB 库名", "QuestDB", "qdb"),
    ConfigFieldSpec(
        "ANALYSIS_REPORT_FALLBACK",
        "分析报告回退源",
        "其他",
        "tushare",
        kind="choice",
        choices=("tushare",),
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
        "数据库类型",
        "数据库",
        "sqlite",
        kind="choice",
        choices=("sqlite", "questdb"),
    ),
    ConfigFieldSpec("database.host", "数据库主机", "数据库", ""),
    ConfigFieldSpec("database.port", "数据库端口", "数据库", "0", kind="int"),
    ConfigFieldSpec("database.http_port", "QuestDB HTTP 端口", "数据库", "9000", kind="int"),
    ConfigFieldSpec("database.user", "数据库用户名", "数据库", ""),
    ConfigFieldSpec("database.password", "数据库密码", "数据库", "", sensitive=True),
    ConfigFieldSpec("database.database", "数据库名", "数据库", "database.db"),
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

ENV_QUESTDB_KEYS: frozenset[str] = frozenset(
    spec.key for spec in ENV_CONFIG_SPECS if spec.group == "QuestDB"
)
ENV_DB_KEYS: frozenset[str] = frozenset({"DATABASE_NAME"}) | ENV_QUESTDB_KEYS

VT_DB_SPECS: tuple[ConfigFieldSpec, ...] = tuple(
    spec for spec in VT_CONFIG_SPECS if spec.key.startswith("database.")
)
VT_NON_DB_SPECS: tuple[ConfigFieldSpec, ...] = tuple(
    spec for spec in VT_CONFIG_SPECS if not spec.key.startswith("database.")
)
VT_QUESTDB_KEYS: frozenset[str] = frozenset(
    spec.key
    for spec in VT_DB_SPECS
    if spec.key not in {"database.name", "database.database"}
)
VT_SQLITE_KEYS: frozenset[str] = frozenset({"database.name", "database.database"})


def normalize_database_name(name: str) -> str:
    text = name.strip().lower()
    return text if text in {"sqlite", "questdb"} else "sqlite"
