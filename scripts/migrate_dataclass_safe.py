#!/usr/bin/env python3
"""仅迁移 @dataclass 装饰的 class 定义（不误伤函数签名）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "packages" / "vnpy-ashare" / "vnpy_ashare"

FIELD_DESC: dict[str, str] = {
    "symbol": "六位股票代码",
    "exchange": "交易所代码",
    "name": "名称",
    "vt_symbol": "VeighNa 合约代码",
    "title": "标题",
    "status": "状态",
    "message": "说明信息",
    "rows": "数据行列表",
    "updated_at": "更新时间",
    "created_at": "创建时间",
    "trade_date": "交易日",
    "price": "价格",
    "volume": "成交量",
    "amount": "金额",
    "change_pct": "涨跌幅（%）",
    "text": "文本内容",
    "key": "键名",
    "config": "配置项",
    "enabled": "是否启用",
    "source": "数据来源",
    "count": "数量",
    "start": "开始日期",
    "end": "结束日期",
    "notes": "备注",
    "success": "是否成功",
    "payload": "载荷对象",
    "prompt": "提示词",
    "kind": "类型标识",
    "label": "展示标签",
    "value": "数值",
    "id": "主键 ID",
    "body": "正文",
    "error": "错误信息",
    "ts_code": "Tushare 代码",
    "macd": "MACD 值",
    "dif": "DIF 值",
    "dea": "DEA 值",
    "rsi": "RSI 值",
    "industry": "所属行业",
    "pe_ttm": "市盈率 TTM",
    "roe": "净资产收益率",
    "main_net": "主力净流入",
}


def desc(name: str) -> str:
    return FIELD_DESC.get(name, name.replace("_", " "))


def field_line(name: str, type_ann: str, default: str | None) -> str:
    d = desc(name)
    if default is None:
        return f"    {name}: {type_ann} = Field(description=\"{d}\")"
    if default.startswith("field("):
        if "default_factory=list" in default:
            return f"    {name}: {type_ann} = Field(default_factory=list, description=\"{d}\")"
        if "default_factory=dict" in default:
            return f"    {name}: {type_ann} = Field(default_factory=dict, description=\"{d}\")"
        if "default_factory=set" in default:
            return f"    {name}: {type_ann} = Field(default_factory=set, description=\"{d}\")"
    return f"    {name}: {type_ann} = Field(default={default}, description=\"{d}\")"


def migrate_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "@dataclass" not in text:
        return False

    lines = text.splitlines()
    out: list[str] = []
    i = 0
    frozen_pending = False
    mutable_pending = False
    in_dataclass = False
    class_indent = 0
    changed = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("@dataclass(frozen=True)"):
            frozen_pending = True
            mutable_pending = False
            changed = True
            i += 1
            continue
        if stripped == "@dataclass":
            mutable_pending = True
            frozen_pending = False
            changed = True
            i += 1
            continue

        class_match = re.match(r"^(\s*)class (\w+)(\([^)]*\))?:\s*$", line)
        if class_match and (frozen_pending or mutable_pending):
            indent, name, bases = class_match.group(1), class_match.group(2), class_match.group(3)
            base = "FrozenModel" if frozen_pending else "MutableModel"
            if bases:
                out.append(f"{indent}class {name}{bases}:")
            else:
                out.append(f"{indent}class {name}({base}):")
            in_dataclass = True
            class_indent = len(indent)
            frozen_pending = mutable_pending = False
            i += 1
            continue

        if in_dataclass:
            if stripped and not line.startswith(" " * (class_indent + 1)) and not stripped.startswith("#"):
                in_dataclass = False
            elif stripped.startswith("def ") or stripped.startswith("@") or stripped.startswith("class "):
                in_dataclass = False
            else:
                ann = re.match(
                    r"^(\s+)(\w+):\s*([^=]+?)\s*=\s*field\((.+)\)\s*$",
                    line,
                )
                if ann:
                    out.append(field_line(ann.group(2), ann.group(3).strip(), f"field({ann.group(4)})"))
                    changed = True
                    i += 1
                    continue
                ann_def = re.match(r"^(\s+)(\w+):\s*([^=]+?)\s*=\s*(.+?)\s*$", line)
                if ann_def and "Field(" not in line:
                    out.append(field_line(ann_def.group(2), ann_def.group(3).strip(), ann_def.group(4).strip()))
                    changed = True
                    i += 1
                    continue
                ann_req = re.match(r"^(\s+)(\w+):\s*([^#\n]+?)\s*$", line)
                if (
                    ann_req
                    and "Field(" not in line
                    and ann_req.group(2) not in ("model_config",)
                    and not ann_req.group(3).strip().endswith(":")
                ):
                    out.append(field_line(ann_req.group(2), ann_req.group(3).strip(), None))
                    changed = True
                    i += 1
                    continue

        out.append(line)
        i += 1

    new_text = "\n".join(out) + ("\n" if text.endswith("\n") else "")

    if "from pydantic import Field" not in new_text:
        new_text = new_text.replace(
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\nfrom pydantic import Field\n\n",
            1,
        )
    if "from vnpy_ashare.domain.base import" not in new_text:
        if "FrozenModel" in new_text:
            imp = "from vnpy_ashare.domain.base import FrozenModel, MutableModel\n\n"
        else:
            imp = "from vnpy_ashare.domain.base import MutableModel\n\n"
        new_text = new_text.replace("from pydantic import Field\n\n", f"from pydantic import Field\n\n{imp}", 1)

    new_text = re.sub(r"from dataclasses import dataclass, field\n", "", new_text)
    new_text = re.sub(r"from dataclasses import field, dataclass\n", "", new_text)
    new_text = re.sub(r"from dataclasses import dataclass\n", "", new_text)
    new_text = re.sub(r"from dataclasses import field\n", "", new_text)

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return changed


def main() -> int:
    n = 0
    for path in sorted(ROOT.rglob("*.py")):
        if migrate_file(path):
            print(path.relative_to(ROOT))
            n += 1
    print(f"done: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
