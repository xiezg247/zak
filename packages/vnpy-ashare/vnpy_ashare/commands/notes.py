"""个股笔记 CLI 导出。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import Mock

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.services.note import NoteService
from vnpy_common.paths import BACKUP_DIR


def _note_service() -> NoteService:
    engine = Mock()
    engine.main_engine = None
    engine.event_engine = None
    return NoteService(engine)


def _cmd_export(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    service = _note_service()
    if args.symbol:
        item = parse_stock_symbol(args.symbol)
        if item is None:
            print(f"无法解析代码: {args.symbol}", file=sys.stderr)
            return 1
        path = service.export_symbol_markdown(
            item.symbol,
            item.exchange,
            out_dir,
            name=args.name or item.name,
        )
        if path is None:
            print(f"无笔记内容: {item.vt_symbol}")
            return 0
        print(f"已导出 -> {path}")
        return 0

    paths = service.export_all_markdown(out_dir)
    if not paths:
        print("暂无个股笔记可导出")
        return 0
    print(f"已导出 {len(paths)} 个文件 -> {out_dir}")
    for path in paths[:10]:
        print(f"  {path.name}")
    if len(paths) > 10:
        print(f"  ... 共 {len(paths)} 个")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    notes = subparsers.add_parser("notes", help="个股笔记导出")
    notes_sub = notes.add_subparsers(dest="notes_command", required=True)

    export_cmd = notes_sub.add_parser("export", help="导出 Markdown")
    export_cmd.add_argument("--out-dir", default=str(BACKUP_DIR / "notes"), help="输出目录")
    export_cmd.add_argument("--symbol", help="仅导出单票，如 600519.SSE")
    export_cmd.add_argument("--name", default="", help="导出标题中的名称")
    export_cmd.set_defaults(handler=_cmd_export)
