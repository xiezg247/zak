#!/usr/bin/env python3
"""将函数体内的 import 提升到模块顶部（配合 Ruff PLC0415）。"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path


def _module_insert_line(lines: list[str]) -> int:
    """在 docstring / __future__ 之后返回插入行号。"""
    idx = 0
    if lines and lines[0].startswith("#!"):
        idx = 1
    while idx < len(lines) and (lines[idx].strip() == "" or lines[idx].strip().startswith("#")):
        idx += 1
    if idx < len(lines) and (
        lines[idx].strip().startswith('"""') or lines[idx].strip().startswith("'''")
    ):
        quote = lines[idx].strip()[:3]
        if lines[idx].count(quote) >= 2 and lines[idx].strip() != quote:
            idx += 1
        else:
            idx += 1
            while idx < len(lines) and quote not in lines[idx]:
                idx += 1
            idx += 1
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx < len(lines) and lines[idx].strip() == "from __future__ import annotations":
        idx += 1
        while idx < len(lines) and lines[idx].strip() == "":
            idx += 1
    return idx


def _collect_nested_imports(node: ast.AST) -> list[tuple[int, str]]:
    """收集模块级函数/方法体内的 import 行（不含 TYPE_CHECKING 块）。"""
    found: list[tuple[int, str]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._in_type_checking = False
            self._in_function = 0

        def visit_If(self, node: ast.If) -> None:
            is_tc = (
                isinstance(node.test, ast.Name)
                and node.test.id == "TYPE_CHECKING"
            ) or (
                isinstance(node.test, ast.Attribute)
                and isinstance(node.test.value, ast.Name)
                and node.test.value.id == "typing"
                and node.test.attr == "TYPE_CHECKING"
            )
            if is_tc:
                return
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._in_function += 1
            self.generic_visit(node)
            self._in_function -= 1

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._in_function += 1
            self.generic_visit(node)
            self._in_function -= 1

        def visit_Import(self, node: ast.Import) -> None:
            if self._in_function > 0:
                found.append((node.lineno, ast.unparse(node)))

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if self._in_function > 0:
                found.append((node.lineno, ast.unparse(node)))

    Visitor().visit(node)
    return found


def hoist_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    nested = _collect_nested_imports(tree)
    if not nested:
        return False

    lines = source.splitlines(keepends=True)
    import_lines = sorted({stmt for _, stmt in nested})

    # 自底向上删除原 import 行
    for lineno, _ in sorted(nested, key=lambda item: item[0], reverse=True):
        idx = lineno - 1
        if 0 <= idx < len(lines):
            del lines[idx]

    insert_at = _module_insert_line(lines)
    block = [line if line.endswith("\n") else line + "\n" for line in import_lines]
    if insert_at > 0 and lines[insert_at - 1].strip() != "":
        block = ["\n", *block]
    if insert_at < len(lines) and lines[insert_at].strip() != "":
        block = [*block, "\n"]

    lines[insert_at:insert_at] = block
    path.write_text("".join(lines), encoding="utf-8")
    return True


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("packages/vnpy-ashare")
    proc = subprocess.run(
        [
            "uv",
            "run",
            "ruff",
            "check",
            str(root),
            "--select",
            "PLC0415",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        violations = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        print(proc.stdout or proc.stderr)
        return 1

    files = sorted({v["filename"] for v in violations})
    changed = 0
    for filepath in files:
        if hoist_file(Path(filepath)):
            changed += 1
    print(f"hoisted imports in {changed}/{len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
