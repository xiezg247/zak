#!/usr/bin/env python3
"""将 vnpy_ashare 中残留的 @dataclass 批量迁移为 Pydantic（含 Field description）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "packages" / "vnpy-ashare" / "vnpy_ashare"

FIELD_DESC: dict[str, str] = {
    "symbol": "六位股票代码",
    "exchange": "交易所代码",
    "name": "名称",
    "id": "主键 ID",
    "title": "标题",
    "body": "正文",
    "status": "状态",
    "message": "说明信息",
    "error": "错误信息",
    "source": "数据来源",
    "kind": "类型标识",
    "label": "展示标签",
    "value": "数值",
    "count": "数量",
    "rows": "数据行列表",
    "columns": "列定义",
    "updated_at": "更新时间",
    "created_at": "创建时间",
    "trade_date": "交易日",
    "vt_symbol": "VeighNa 合约代码",
    "price": "价格",
    "volume": "成交量",
    "amount": "金额",
    "change_pct": "涨跌幅（%）",
    "notes": "备注",
    "success": "是否成功",
    "payload": "载荷对象",
    "prompt": "提示词",
    "text": "文本内容",
    "config": "配置项",
    "enabled": "是否启用",
    "key": "键名",
    "default": "默认值",
    "description": "说明",
    "group": "分组",
    "choices": "可选值列表",
    "sensitive": "是否敏感",
    "template_id": "模板标识",
    "class_name": "类名",
    "start": "开始日期",
    "end": "结束日期",
    "history": "历史记录列表",
    "latest": "最新记录",
    "ts_code": "Tushare 代码",
    "macd": "MACD 值",
    "dif": "DIF 值",
    "dea": "DEA 值",
    "rsi": "RSI 值",
    "industry": "所属行业",
    "pe_ttm": "市盈率 TTM",
    "roe": "净资产收益率",
    "main_net": "主力净流入",
    "net_mf_amount": "主力净流入金额",
    "buy_elg_amount": "特大单买入金额",
    "sell_elg_amount": "特大单卖出金额",
}


def field_description(name: str) -> str:
    return FIELD_DESC.get(name, f"{name.replace('_', ' ')}")


def convert_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "@dataclass" not in text:
        return False

    original = text

    # 移除 dataclass 相关 import
    text = re.sub(r"from dataclasses import dataclass, field\n", "", text)
    text = re.sub(r"from dataclasses import field, dataclass\n", "", text)
    text = re.sub(r"from dataclasses import dataclass\n", "", text)
    text = re.sub(r"from dataclasses import field\n", "", text)

    # 确保 pydantic / base import
    if "from pydantic import Field" not in text:
        if "from __future__ import annotations" in text:
            text = text.replace(
                "from __future__ import annotations\n\n",
                "from __future__ import annotations\n\nfrom pydantic import Field\n\n",
                1,
            )
        else:
            text = "from pydantic import Field\n\n" + text

    needs_frozen = "FrozenModel" in text or "@dataclass(frozen=True)" in original
    needs_mutable = "MutableModel" in text or ("@dataclass\n" in original and "@dataclass(frozen=True)" not in original)
    if "@dataclass(frozen=True)" in original:
        needs_frozen = True
    if re.search(r"^@dataclass\s*$", original, re.MULTILINE):
        needs_mutable = True

    base_import = "from vnpy_ashare.domain.base import "
    bases: list[str] = []
    if needs_frozen:
        bases.append("FrozenModel")
    if needs_mutable:
        bases.append("MutableModel")
    if not bases:
        bases = ["FrozenModel"]

    import_line = base_import + ", ".join(dict.fromkeys(bases)) + "\n"
    if "from vnpy_ashare.domain.base import" not in text:
        text = text.replace("from pydantic import Field\n\n", f"from pydantic import Field\n\n{import_line}\n", 1)

    # @dataclass(frozen=True) -> remove
    text = re.sub(r"@dataclass\(frozen=True\)\n", "", text)
    text = re.sub(r"@dataclass\n", "", text)

    # class Foo: -> class Foo(FrozenModel):  (仅无基类的 class)
    def add_base(match: re.Match[str]) -> str:
        indent, name = match.group(1), match.group(2)
        base = "FrozenModel" if "@dataclass(frozen=True)" in original else "MutableModel"
        return f"{indent}class {name}({base}):"

    text = re.sub(r"^(\s*)class (\w+):\s*$", add_base, text, flags=re.MULTILINE)

    # field(default_factory=list) -> Field(default_factory=list, description="...")
    text = re.sub(
        r"(\w+):\s*list\[([^\]]+)\]\s*=\s*field\(default_factory=list\)",
        lambda m: f'{m.group(1)}: list[{m.group(2)}] = Field(default_factory=list, description="{field_description(m.group(1))}")',
        text,
    )
    text = re.sub(
        r"(\w+):\s*dict\[([^\]]+)\]\s*=\s*field\(default_factory=dict\)",
        lambda m: f'{m.group(1)}: dict[{m.group(2)}] = Field(default_factory=dict, description="{field_description(m.group(1))}")',
        text,
    )

    # name: type = default
    text = re.sub(
        r"^(\s+)(\w+):\s*([^=\n]+?)\s*=\s*([^#\n]+)$",
        lambda m: (
            f'{m.group(1)}{m.group(2)}: {m.group(3).strip()} = Field(default={m.group(4).strip()}, description="{field_description(m.group(2))}")'
            if "Field(" not in m.group(0)
            else m.group(0)
        ),
        text,
        flags=re.MULTILINE,
    )

    # name: type  (required, no default)
    text = re.sub(
        r"^(\s+)(\w+):\s*([^=\n#]+)$",
        lambda m: (
            f'{m.group(1)}{m.group(2)}: {m.group(3).strip()} = Field(description="{field_description(m.group(2))}")'
            if "Field(" not in m.group(0) and m.group(3).strip() not in ("",) and not m.group(2).startswith("_") and m.group(2) not in ("model_config",)
            else m.group(0)
        ),
        text,
        flags=re.MULTILINE,
    )

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    for path in sorted(ROOT.rglob("*.py")):
        if path.name == "base.py" and "domain" in path.parts:
            continue
        if convert_file(path):
            print(f"converted: {path.relative_to(ROOT)}")
            changed += 1
    print(f"total: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
