#!/usr/bin/env python3
"""将 hoist_plc0415 误提升到模块顶的 import 还原到原函数内（附 noqa: PLC0415）。"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path


def _collect_nested_imports(node: ast.AST) -> dict[str, list[int]]:
    """import 语句 -> 所在函数体内的行号列表（HEAD）。"""
    found: dict[str, list[int]] = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._in_function = 0

        def visit_If(self, node: ast.If) -> None:
            is_tc = isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
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
                found.setdefault(ast.unparse(node), []).append(node.lineno)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if self._in_function > 0:
                found.setdefault(ast.unparse(node), []).append(node.lineno)

    Visitor().visit(node)
    return found


def _module_level_imports(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for child in node.body:
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            found.add(ast.unparse(child))
    return found


def _function_for_line(tree: ast.AST, lineno: int) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    best: ast.FunctionDef | ast.AsyncFunctionDef | None = None

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            nonlocal best
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                best = node
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            nonlocal best
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                best = node
            self.generic_visit(node)

    Visitor().visit(tree)
    return best


def revert_file(path: Path, head_source: str, current_source: str) -> bool:
    try:
        head_tree = ast.parse(head_source)
        current_tree = ast.parse(current_source)
    except SyntaxError:
        return False

    nested = _collect_nested_imports(head_tree)
    if not nested:
        return False

    module_imports = _module_level_imports(current_tree)
    to_revert = sorted(stmt for stmt in nested if stmt in module_imports)
    if not to_revert:
        return False

    lines = current_source.splitlines(keepends=True)

    # 删除模块顶部的 import
    for child in list(current_tree.body):
        if isinstance(child, (ast.Import, ast.ImportFrom)) and ast.unparse(child) in to_revert:
            idx = child.lineno - 1
            if 0 <= idx < len(lines):
                del lines[idx]
                # 清理多余空行
                if idx < len(lines) and lines[idx].strip() == "" and idx > 0 and lines[idx - 1].strip() == "":
                    del lines[idx]

    current_tree = ast.parse("".join(lines))

    for stmt in to_revert:
        head_lineno = nested[stmt][0]
        func = _function_for_line(head_tree, head_lineno)
        if func is None:
            continue
        func_name = func.name
        # 在当前 AST 中找同名函数
        target_func: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        for node in ast.walk(current_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                target_func = node
                break
        if target_func is None or not target_func.body:
            continue
        insert_at = target_func.body[0].lineno - 1
        indent = " " * (target_func.col_offset + 4)
        import_line = f"{indent}{stmt}  # noqa: PLC0415\n"
        if insert_at < len(lines) and lines[insert_at].strip().startswith(('"""', "'''")):
            # 跳过 docstring
            insert_at = target_func.body[0].end_lineno or insert_at
        lines.insert(insert_at, import_line)

    path.write_text("".join(lines), encoding="utf-8")
    return True


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        ["git", "diff", "--name-only", "packages/vnpy-ashare"],
        capture_output=True,
        text=True,
        cwd=repo,
    )
    files = [repo / line.strip() for line in proc.stdout.splitlines() if line.strip().endswith(".py")]
    changed = 0
    for path in files:
        if not path.exists():
            continue
        head = subprocess.run(
            ["git", "show", f"HEAD:{path.relative_to(repo)}"],
            capture_output=True,
            text=True,
            cwd=repo,
        )
        if head.returncode != 0:
            continue
        current = path.read_text(encoding="utf-8")
        if revert_file(path, head.stdout, current):
            changed += 1
            print(path.relative_to(repo))
    print(f"reverted hoisted imports in {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
