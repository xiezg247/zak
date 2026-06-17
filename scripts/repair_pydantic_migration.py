#!/usr/bin/env python3
"""修复 migrate_dataclass_to_pydantic.py 误伤函数签名的问题。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "packages" / "vnpy-ashare" / "vnpy_ashare"


def repair(text: str) -> str:
    # 函数/方法参数：name: type, = Field(...) -> name: type,
    text = re.sub(
        r"^(\s+)(\w+):\s*([^=\n]+?),\s*=\s*Field\([^)]*\)\s*$",
        r"\1\2: \3,",
        text,
        flags=re.MULTILINE,
    )
    # 函数参数末尾无逗号：name: type = Field(...) 在 def 行内 - 已由上行处理

    # 局部变量误加 Field
    text = re.sub(
        r"^(\s+\w+:\s*[^=\n]+)=\s*Field\(default=\[\],\s*description=\"[^\"]*\"\)\s*$",
        r"\1= []",
        text,
        flags=re.MULTILINE,
    )

    # 双逗号
    text = text.replace("default=None,,", "default=None,")
    text = text.replace("default_factory=list,,", "default_factory=list,")

    return text


def main() -> int:
    changed = 0
    for path in sorted(ROOT.rglob("*.py")):
        original = path.read_text(encoding="utf-8")
        fixed = repair(original)
        if fixed != original:
            path.write_text(fixed, encoding="utf-8")
            changed += 1
    print(f"repaired: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
