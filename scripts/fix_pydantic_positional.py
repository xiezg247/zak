#!/usr/bin/env python3
"""将 Pydantic 模型的位置参数构造改为关键字参数（仅处理简单字面量调用）。"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "packages" / "vnpy-ashare" / "vnpy_ashare"


def field_names_for_class(source: str, class_name: str) -> list[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            names: list[str] = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    names.append(item.target.id)
            return names
    return []


def convert_call(text: str, class_name: str, fields: list[str]) -> str:
    pattern = re.compile(
        rf"{re.escape(class_name)}\((.*?)\)(?=[,\n\)])",
        re.DOTALL,
    )

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if not inner or "=" in inner.split(",")[0]:
            return match.group(0)
        try:
            node = ast.parse(f"__wrapper__({inner})", mode="eval")
        except SyntaxError:
            return match.group(0)
        call = node.body  # type: ignore[assignment]
        if not isinstance(call, ast.Call):
            return match.group(0)
        args = call.args
        if not args:
            return match.group(0)
        kw = list(call.keywords)
        if len(args) > len(fields):
            return match.group(0)
        parts: list[str] = []
        for name, arg in zip(fields, args, strict=True):
            parts.append(f"{name}={ast.unparse(arg)}")
        for kwarg in kw:
            parts.append(f"{kwarg.arg}={ast.unparse(kwarg.value)}")
        return f"{class_name}({', '.join(parts)})"

    return pattern.sub(repl, text)


def process_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    if "FrozenModel" not in source and "MutableModel" not in source:
        return False
    tree = ast.parse(source)
    classes = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            (isinstance(base, ast.Name) and base.id in {"FrozenModel", "MutableModel"})
            or (isinstance(base, ast.Attribute) and base.attr in {"FrozenModel", "MutableModel"})
            for base in node.bases
        )
    ]
    new_source = source
    changed = False
    for cls in classes:
        fields = field_names_for_class(source, cls)
        if not fields:
            continue
        updated = convert_call(new_source, cls, fields)
        if updated != new_source:
            new_source = updated
            changed = True
    if changed:
        path.write_text(new_source, encoding="utf-8")
    return changed


def main() -> int:
    n = 0
    for path in sorted(ROOT.rglob("*.py")):
        if process_file(path):
            print(path.relative_to(ROOT))
            n += 1
    print(f"fixed: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
