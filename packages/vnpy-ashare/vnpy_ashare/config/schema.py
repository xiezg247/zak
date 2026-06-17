"""项目可配置项定义（.env + vt_setting.json）。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from vnpy_ashare.config.fonts import default_font_family
from vnpy_ashare.domain.base import FrozenModel
from vnpy_llm.config import DEFAULT_BASE_URL, DEFAULT_MODEL

ValueKind = Literal["text", "secret", "bool", "int", "choice"]
ConfigSource = Literal["env", "default", "vt_file"]


class ConfigFieldSpec(FrozenModel):
    key: str = Field(description="配置键名")
    label: str = Field(description="展示标签")
    group: str = Field(description="配置分组")
    default: str = Field(description="默认值")
    sensitive: bool = Field(default=False, description="是否为敏感字段")
    kind: ValueKind = Field(default="text", description="值类型")
    choices: tuple[str, ...] = Field(default_factory=tuple, description="可选值列表")
    description: str = Field(default="", description="字段说明")


ENV_CONFIG_SPECS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        key="TICKFLOW_API_KEY", label="TickFlow API Key", group="数据源", default="", sensitive=True, description="主行情数据源，https://tickflow.org"
    ),
    ConfigFieldSpec(key="TUSHARE_TOKEN", label="Tushare Token", group="数据源", default="", sensitive=True, description="财务/选股辅助，https://tushare.pro"),
    ConfigFieldSpec(
        key="DATAFEED_NAME",
        label="默认行情数据源",
        group="数据源",
        default="tickflow",
        kind="choice",
        choices=("tickflow", "tushare"),
    ),
    ConfigFieldSpec(
        key="DATABASE_NAME",
        label="K 线数据库类型",
        group="数据库",
        default="sqlite",
        kind="choice",
        choices=("sqlite", "postgresql"),
    ),
    ConfigFieldSpec(
        key="REDIS_URL",
        label="Redis URL",
        group="Redis 行情",
        default="redis://127.0.0.1:6379/0",
        description="例：redis://127.0.0.1:6379/0 或 redis://:password@host:6379/0",
    ),
    ConfigFieldSpec(key="QUOTE_COLLECT_INTERVAL", label="行情采集间隔（秒）", group="Redis 行情", default="15", kind="int"),
    ConfigFieldSpec(key="LLM_API_BASE", label="LLM API Base", group="大模型", default=DEFAULT_BASE_URL),
    ConfigFieldSpec(key="LLM_API_KEY", label="LLM API Key", group="大模型", default="", sensitive=True),
    ConfigFieldSpec(key="LLM_MODEL", label="LLM Model", group="大模型", default=DEFAULT_MODEL),
    ConfigFieldSpec(key="LLM_MAX_TOKENS", label="LLM Max Tokens", group="大模型", default="4096", kind="int"),
    ConfigFieldSpec(key="LLM_TEMPERATURE", label="LLM Temperature", group="大模型", default="0.7"),
    ConfigFieldSpec(key="POSTGRES_HOST", label="PostgreSQL 主机", group="PostgreSQL", default="localhost"),
    ConfigFieldSpec(key="POSTGRES_PORT", label="PostgreSQL 端口", group="PostgreSQL", default="5432", kind="int"),
    ConfigFieldSpec(key="POSTGRES_USER", label="PostgreSQL 用户名", group="PostgreSQL", default="zak"),
    ConfigFieldSpec(key="POSTGRES_PASSWORD", label="PostgreSQL 密码", group="PostgreSQL", default="zak", sensitive=True),
    ConfigFieldSpec(key="POSTGRES_DATABASE", label="PostgreSQL 库名", group="PostgreSQL", default="zak"),
    ConfigFieldSpec(
        key="NOTIFY_ENABLED", label="启用消息通知", group="消息通知", default="false", kind="bool", description="开启后按下方事件订阅向飞书 Webhook 推送"
    ),
    ConfigFieldSpec(
        key="FEISHU_WEBHOOK_URL",
        label="飞书 Webhook URL",
        group="消息通知",
        default="",
        sensitive=True,
        description="飞书群 → 设置 → 群机器人 → 添加自定义机器人",
    ),
    ConfigFieldSpec(
        key="FEISHU_WEBHOOK_SECRET",
        label="飞书签名校验 Secret",
        group="消息通知",
        default="",
        sensitive=True,
        description="机器人开启签名校验时填写；留空则不签名",
    ),
    ConfigFieldSpec(
        key="NOTIFY_MIN_INTERVAL_SEC", label="通知最小间隔（秒）", group="消息通知", default="30", kind="int", description="两次出站之间的最短间隔，默认 30"
    ),
    ConfigFieldSpec(
        key="NOTIFY_FEISHU_INTERACTIVE",
        label="飞书 interactive 卡片",
        group="消息通知",
        default="true",
        kind="bool",
        description="true 时发送卡片消息；可被 QSettings 覆盖",
    ),
    ConfigFieldSpec(key="NOTIFY_OPEN_URL", label="卡片按钮链接", group="消息通知", default="", description="可选；配置后卡片底部显示「打开 zak」按钮"),
)

VT_CONFIG_SPECS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        key="datafeed.name",
        label="数据源",
        group="数据服务",
        default="tickflow",
        kind="choice",
        choices=("tickflow", "tushare"),
    ),
    ConfigFieldSpec(key="datafeed.username", label="数据源用户名", group="数据服务", default="api_key"),
    ConfigFieldSpec(key="datafeed.password", label="API Key / Token", group="数据服务", default="", sensitive=True),
    ConfigFieldSpec(
        key="database.name",
        label="K 线数据库类型",
        group="K 线",
        default="sqlite",
        kind="choice",
        choices=("sqlite", "postgresql"),
    ),
    ConfigFieldSpec(key="database.host", label="PostgreSQL 主机", group="K 线", default=""),
    ConfigFieldSpec(key="database.port", label="PostgreSQL 端口", group="K 线", default="0", kind="int"),
    ConfigFieldSpec(key="database.user", label="PostgreSQL 用户名", group="K 线", default=""),
    ConfigFieldSpec(key="database.password", label="PostgreSQL 密码", group="K 线", default="", sensitive=True),
    ConfigFieldSpec(key="database.database", label="K 线 SQLite 文件", group="K 线", default="database.db"),
    ConfigFieldSpec(
        key="database.meta.app", label="元数据 SQLite 文件", group="元数据", default="zak.db", description="相对 ~/.vntrader/；自选、universe、回测/选股历史"
    ),
    ConfigFieldSpec(
        key="database.meta.chat", label="AI 对话 SQLite 文件", group="元数据", default="llm_chat.db", description="相对 ~/.vntrader/；不受 database.name 影响"
    ),
    ConfigFieldSpec(key="font.family", label="字体", group="界面与日志", default=default_font_family()),
    ConfigFieldSpec(key="font.size", label="字号", group="界面与日志", default="12", kind="int"),
    ConfigFieldSpec(key="log.active", label="启用日志", group="界面与日志", default="true", kind="bool"),
    ConfigFieldSpec(
        key="log.level",
        label="日志级别",
        group="界面与日志",
        default="INFO",
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
    {
        "NOTIFY_ENABLED",
        "FEISHU_WEBHOOK_URL",
        "FEISHU_WEBHOOK_SECRET",
        "NOTIFY_MIN_INTERVAL_SEC",
        "NOTIFY_FEISHU_INTERACTIVE",
        "NOTIFY_OPEN_URL",
    },
)

ENV_SPEC_BY_KEY: dict[str, ConfigFieldSpec] = {spec.key: spec for spec in ENV_CONFIG_SPECS}
ENV_GENERAL_SPECS: tuple[ConfigFieldSpec, ...] = tuple(spec for spec in ENV_CONFIG_SPECS if spec.key not in ENV_DB_KEYS and spec.key not in ENV_NOTIFY_KEYS)
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
