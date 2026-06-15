"""`.env` 文件读写（配置页编辑入口）。"""

from __future__ import annotations

from pathlib import Path

from vnpy_ashare.config.bridge import load_effective_env_values, parse_env_file
from vnpy_ashare.config.schema import ENV_CONFIG_SPECS
from vnpy_common.paths import ENV_FILE


def quote_env_value(value: str) -> str:
    text = str(value)
    if not text:
        return ""
    if any(ch.isspace() for ch in text) or any(ch in {'#', "=", '"', "'"} for ch in text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def env_assignment_line(key: str, value: str) -> str:
    return f"{key}={quote_env_value(value)}"


def _parse_env_line(raw_line: str) -> tuple[str | None, str]:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None, raw_line
    line = stripped[7:].strip() if stripped.startswith("export ") else stripped
    key, _, _value = line.partition("=")
    key = key.strip()
    if not key:
        return None, raw_line
    return key, raw_line


def save_env_values(
    values: dict[str, str],
    *,
    env_file: Path = ENV_FILE,
    backup: bool = True,
) -> Path:
    """将 schema 内环境变量写入 .env，保留未知键与注释行。"""
    known = {spec.key for spec in ENV_CONFIG_SPECS}
    merged = load_effective_env_values(env_file)
    for key, value in values.items():
        if key in known:
            merged[key] = str(value)

    existing_file = parse_env_file(env_file)
    existing_lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.is_file() else []

    output: list[str] = []
    replaced: set[str] = set()

    for raw_line in existing_lines:
        key, _original = _parse_env_line(raw_line)
        if key is None or key not in known:
            output.append(raw_line)
            continue
        replaced.add(key)
        new_val = merged.get(key, "")
        if new_val or key in existing_file or key in values:
            output.append(env_assignment_line(key, new_val))

    for spec in ENV_CONFIG_SPECS:
        if spec.key in replaced:
            continue
        new_val = merged.get(spec.key, spec.default)
        should_write = spec.key in values or spec.key in existing_file
        if not should_write and new_val and new_val != spec.default:
            should_write = True
        if should_write and (new_val or spec.key in values):
            output.append(env_assignment_line(spec.key, new_val))

    env_file.parent.mkdir(parents=True, exist_ok=True)
    if backup and env_file.is_file():
        backup_path = env_file.with_name(f"{env_file.name}.bak")
        if backup_path.exists():
            backup_path.unlink()
        env_file.rename(backup_path)

    content = "\n".join(output).rstrip()
    env_file.write_text(f"{content}\n" if content else "", encoding="utf-8")
    return env_file
