#!/usr/bin/env python3
"""同步官方 Agent Skills 到 skills/ 目录。

来源：
- https://github.com/waditu-tushare/skills  → skills/tushare-data
- https://github.com/tickflow-org/tickflow-skills → skills/tickflow

用法：
    uv run python scripts/sync_skills.py
    uv run python scripts/sync_skills.py --list
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = PROJECT_ROOT / "skills"

OFFICIAL_SKILLS: list[tuple[str, str, str, str]] = [
    (
        "https://github.com/waditu-tushare/skills.git",
        "master",
        "tushare-data",
        "tushare-data",
    ),
    (
        "https://github.com/tickflow-org/tickflow-skills.git",
        "main",
        "tickflow",
        "tickflow",
    ),
]


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def sync_one(repo: str, branch: str, src_dir: str, dest_name: str) -> Path:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SKILLS_DIR / dest_name

    with tempfile.TemporaryDirectory(prefix="vnpy_skills_") as tmp:
        clone_root = Path(tmp) / "repo"
        _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                branch,
                repo,
                str(clone_root),
            ]
        )
        src = clone_root / src_dir
        if not src.is_dir():
            raise FileNotFoundError(f"仓库中不存在目录: {src_dir}")

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    print(f"✓ {dest_name} -> {dest}")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="同步官方 Agent Skills")
    parser.add_argument(
        "--list",
        action="store_true",
        help="仅列出将同步的 skill",
    )
    parser.add_argument(
        "--only",
        choices=["tushare-data", "tickflow"],
        help="仅同步指定 skill",
    )
    args = parser.parse_args()

    targets = OFFICIAL_SKILLS
    if args.only:
        targets = [t for t in OFFICIAL_SKILLS if t[3] == args.only]

    if args.list:
        for repo, branch, src, dest in targets:
            print(f"{dest}: {repo} ({branch}/{src})")
        return 0

    for repo, branch, src, dest in targets:
        sync_one(repo, branch, src, dest)

    print(f"\n完成。skills 目录: {SKILLS_DIR}")
    print("自编写 Python Skill 可放在 skills/*.py（继承 vnpy_skills.SkillTemplate）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
