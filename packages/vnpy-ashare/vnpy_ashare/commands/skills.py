"""Agent Skills 同步。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from vnpy_common.paths import PROJECT_ROOT

SKILLS_DIR = PROJECT_ROOT / "skills"

OFFICIAL_SKILLS: list[tuple[str, str, str, str]] = [
    ("https://github.com/waditu-tushare/skills.git", "master", "tushare-data", "tushare-data"),
    ("https://github.com/tickflow-org/tickflow-skills.git", "main", "tickflow", "tickflow"),
]


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def _sync_one(repo: str, branch: str, src_dir: str, dest_name: str) -> Path:
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


def _cmd_sync(args: argparse.Namespace) -> int:
    targets = OFFICIAL_SKILLS
    if args.only:
        targets = [item for item in OFFICIAL_SKILLS if item[3] == args.only]

    if args.list:
        for repo, branch, src, dest in targets:
            print(f"{dest}: {repo} ({branch}/{src})")
        return 0

    for repo, branch, src, dest in targets:
        _sync_one(repo, branch, src, dest)

    print(f"\n完成。skills 目录: {SKILLS_DIR}")
    print("自编写 Python Skill 可放在 skills/*.py（继承 vnpy_skills.SkillTemplate）")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    skills = subparsers.add_parser("skills", help="Agent Skills 同步")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)

    sync = skills_sub.add_parser("sync", help="从官方仓库同步 skills/")
    sync.add_argument("--list", action="store_true", help="仅列出将同步的 skill")
    sync.add_argument("--only", choices=["tushare-data", "tickflow"], help="仅同步指定 skill")
    sync.set_defaults(handler=_cmd_sync)
