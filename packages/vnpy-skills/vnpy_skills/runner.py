"""Agent Skill 工具执行：读文件、运行 Python。"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from vnpy_skills.agent_skill import AgentSkill

MAX_OUTPUT_CHARS = 60_000
DEFAULT_TIMEOUT = 90


def read_skill_file(skill: AgentSkill, path: str) -> str:
    if path.strip().lower() == "skill.md":
        return skill.read_file("SKILL.md")
    return skill.read_file(path)


def run_python_in_skill(
    skill: AgentSkill,
    code: str,
    *,
    script_path: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """在 skill 目录下执行 Python 代码或脚本。"""
    cwd = skill.root
    env = os.environ.copy()

    # 注入项目 .env（TUSHARE_TOKEN / TICKFLOW_API_KEY 等）
    try:
        from dotenv import load_dotenv

        from vnpy_common.paths import ENV_FILE

        load_dotenv(ENV_FILE, override=False)
        for key, value in os.environ.items():
            env[key] = value
    except Exception:
        pass

    python = sys.executable

    if script_path.strip():
        target = skill.resolve_path(script_path.strip())
        if target is None or not target.is_file():
            return f"错误：脚本不存在 {script_path}"
        cmd = [python, str(target)]
    else:
        if not code.strip():
            return "错误：code 与 script_path 不能同时为空"
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        cmd = [python, tmp_path]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        parts: list[str] = []
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr}")
        if result.returncode != 0:
            parts.append(f"[exit_code={result.returncode}]")
        output = "\n".join(parts).strip() or "(无输出)"
    except subprocess.TimeoutExpired:
        output = f"错误：执行超时（>{timeout}s）"
    except Exception as ex:
        output = f"错误：{ex}"
    finally:
        if not script_path.strip() and "tmp_path" in locals():
            Path(tmp_path).unlink(missing_ok=True)

    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + f"\n...(已截断，共 {len(output)} 字符)"
    return output
