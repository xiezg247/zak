"""`.env` 与 `vt_setting.json` 映射、构建与漂移检测（单源逻辑）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import Field

from vnpy_ashare.config.fonts import default_font_family
from vnpy_ashare.config.schema import ENV_CONFIG_SPECS, normalize_database_name
from vnpy_common.domain.base import FrozenModel
from vnpy_common.paths import ENV_FILE


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


def load_effective_env_values(env_file: Path = ENV_FILE) -> dict[str, str]:
    """合并 .env 文件与 schema 默认值，得到生效的 ENV 配置。"""
    file_values = parse_env_file(env_file)
    return {spec.key: file_values[spec.key] if spec.key in file_values else spec.default for spec in ENV_CONFIG_SPECS}


def normalize_datafeed_name(name: str) -> str:
    text = name.strip().lower()
    return text if text in {"tickflow", "tushare"} else "tickflow"


def _env_lookup(env: dict[str, str], key: str, default: str = "") -> str:
    if key in env:
        return env[key]
    return default


def postgres_database_settings(env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env or {}
    return {
        "database.name": "postgresql",
        "database.host": _env_lookup(env, "POSTGRES_HOST", "localhost"),
        "database.port": int(_env_lookup(env, "POSTGRES_PORT", "5432") or "5432"),
        "database.user": _env_lookup(env, "POSTGRES_USER", "zak"),
        "database.password": _env_lookup(env, "POSTGRES_PASSWORD", "zak"),
        "database.database": _env_lookup(env, "POSTGRES_DATABASE", "zak"),
    }


def database_settings_from_env(env: dict[str, str]) -> dict[str, Any]:
    return postgres_database_settings(env)


def meta_database_settings(*, env: dict[str, str] | None = None) -> dict[str, str]:
    """业务元数据 / 对话走 PostgreSQL `DATABASE_URL`；vt_setting 不写入本地 DB 路径。"""
    _ = env
    return {}


def datafeed_settings_from_env(env: dict[str, str]) -> dict[str, Any]:
    name = normalize_datafeed_name(_env_lookup(env, "DATAFEED_NAME", "tickflow"))
    if name == "tushare":
        return {
            "datafeed.name": "tushare",
            "datafeed.username": "token",
            "datafeed.password": _env_lookup(env, "TUSHARE_TOKEN", ""),
        }
    return {
        "datafeed.name": "tickflow",
        "datafeed.username": "api_key",
        "datafeed.password": _env_lookup(env, "TICKFLOW_API_KEY", ""),
    }


def base_vt_settings_from_env(env: dict[str, str]) -> dict[str, Any]:
    return {
        "font.family": default_font_family(),
        "font.size": 12,
        "log.active": True,
        "log.level": "INFO",
        **database_settings_from_env(env),
        **meta_database_settings(env=env),
    }


def build_vt_settings_from_env_values(env: dict[str, str]) -> dict[str, Any]:
    """由 .env 键值对生成完整 vt_setting 字典（纯函数，便于测试）。"""
    return {
        **base_vt_settings_from_env(env),
        **datafeed_settings_from_env(env),
    }


def build_vt_settings_from_env_file(env_file: Path = ENV_FILE) -> dict[str, Any]:
    load_dotenv(env_file, override=True)
    env = load_effective_env_values(env_file)
    for key, value in parse_env_file(env_file).items():
        env[key] = os.getenv(key, value)
    return build_vt_settings_from_env_values(env)


class ConfigDrift(FrozenModel):
    """运行时 vt_setting 与 .env 不一致项。"""

    category: str = Field(description="漂移类别")
    env_key: str = Field(description="环境变量键名")
    vt_key: str = Field(description="vt_setting 键名")
    env_value: str = Field(description="环境变量值")
    vt_value: str = Field(description="vt_setting 值")

    @property
    def message(self) -> str:
        return f"{self.vt_key}（运行时 {self.vt_value!r}）与 {self.env_key}（.env {self.env_value!r}）不一致"


def detect_config_drift(
    runtime_settings: dict[str, Any],
    *,
    env_file: Path = ENV_FILE,
) -> list[ConfigDrift]:
    """检测 vt_setting.json 与 .env 之间的关键漂移。"""
    env = load_effective_env_values(env_file)
    drifts: list[ConfigDrift] = []

    env_datafeed = normalize_datafeed_name(env.get("DATAFEED_NAME", "tickflow"))
    vt_datafeed = normalize_datafeed_name(str(runtime_settings.get("datafeed.name", "tickflow")))
    if env_datafeed != vt_datafeed:
        drifts.append(
            ConfigDrift(
                category="datafeed",
                env_key="DATAFEED_NAME",
                vt_key="datafeed.name",
                env_value=env_datafeed,
                vt_value=vt_datafeed,
            )
        )

    env_db = normalize_database_name(env.get("DATABASE_NAME", "postgresql"))
    vt_db = normalize_database_name(str(runtime_settings.get("database.name", "postgresql")))
    if env_db != vt_db:
        drifts.append(
            ConfigDrift(
                category="database",
                env_key="DATABASE_NAME",
                vt_key="database.name",
                env_value=env_db,
                vt_value=vt_db,
            )
        )

    if env_datafeed == vt_datafeed:
        if env_datafeed == "tickflow":
            env_secret = env.get("TICKFLOW_API_KEY", "")
            vt_secret = str(runtime_settings.get("datafeed.password", ""))
            if env_secret != vt_secret:
                drifts.append(
                    ConfigDrift(
                        category="datafeed",
                        env_key="TICKFLOW_API_KEY",
                        vt_key="datafeed.password",
                        env_value=mask_for_display(env_secret),
                        vt_value=mask_for_display(vt_secret),
                    )
                )
        elif env_datafeed == "tushare":
            env_secret = env.get("TUSHARE_TOKEN", "")
            vt_secret = str(runtime_settings.get("datafeed.password", ""))
            if env_secret != vt_secret:
                drifts.append(
                    ConfigDrift(
                        category="datafeed",
                        env_key="TUSHARE_TOKEN",
                        vt_key="datafeed.password",
                        env_value=mask_for_display(env_secret),
                        vt_value=mask_for_display(vt_secret),
                    )
                )

    if env_db == vt_db == "postgresql":
        mapping = (
            ("POSTGRES_HOST", "database.host"),
            ("POSTGRES_PORT", "database.port"),
            ("POSTGRES_USER", "database.user"),
            ("POSTGRES_DATABASE", "database.database"),
        )
        for env_key, vt_key in mapping:
            env_val = env.get(env_key, "")
            vt_val = str(runtime_settings.get(vt_key, ""))
            if str(env_val) != vt_val:
                drifts.append(
                    ConfigDrift(
                        category="database",
                        env_key=env_key,
                        vt_key=vt_key,
                        env_value=env_val,
                        vt_value=vt_val,
                    )
                )
        env_pwd = env.get("POSTGRES_PASSWORD", "")
        vt_pwd = str(runtime_settings.get("database.password", ""))
        if env_pwd != vt_pwd:
            drifts.append(
                ConfigDrift(
                    category="database",
                    env_key="POSTGRES_PASSWORD",
                    vt_key="database.password",
                    env_value=mask_for_display(env_pwd),
                    vt_value=mask_for_display(vt_pwd),
                )
            )

    return drifts


def mask_for_display(value: str) -> str:
    text = value.strip()
    if not text:
        return "（空）"
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}…{text[-4:]}"


def format_config_drift_summary(drifts: list[ConfigDrift], *, max_items: int = 3) -> str:
    if not drifts:
        return ""
    lines = ["检测到 .env 与 vt_setting.json 不一致："]
    for drift in drifts[:max_items]:
        lines.append(f"  · {drift.message}")
    if len(drifts) > max_items:
        lines.append(f"  · 另有 {len(drifts) - max_items} 项…")
    lines.append("可使用「从 .env 同步」覆盖运行时配置。")
    return "\n".join(lines)
