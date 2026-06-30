"""从 Playbook Markdown 解析表格块。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PlaybookTableBlock:
    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")
_SECTION_TITLE_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")


def _parse_table_rows(lines: list[str]) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]] | None:
    table_lines = [line for line in lines if _TABLE_ROW_RE.match(line)]
    if len(table_lines) < 2:
        return None
    if _TABLE_SEP_RE.match(table_lines[1]):
        header_line, data_lines = table_lines[0], table_lines[2:]
    else:
        header_line, data_lines = table_lines[0], table_lines[1:]

    def _cells(line: str) -> tuple[str, ...]:
        return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))

    headers = _cells(header_line)
    rows = tuple(_cells(line) for line in data_lines if line.strip())
    if not headers or not rows:
        return None
    return headers, rows


def parse_playbook_table_blocks(body_md: str) -> tuple[PlaybookTableBlock, ...]:
    """按 **标题** 分段并提取每段内第一个 Markdown 表格。"""
    text = str(body_md or "").strip()
    if not text:
        return ()

    blocks: list[PlaybookTableBlock] = []
    current_title = ""
    current_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_lines, current_title
        if not current_lines:
            return
        parsed = _parse_table_rows(current_lines)
        if parsed is not None:
            headers, rows = parsed
            title = current_title or "规则"
            blocks.append(PlaybookTableBlock(title=title, headers=headers, rows=rows))
        current_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        title_match = _SECTION_TITLE_RE.match(line.strip())
        if title_match:
            _flush()
            current_title = title_match.group(1).strip()
            continue
        current_lines.append(line)

    _flush()

    if blocks:
        return tuple(blocks)

    parsed = _parse_table_rows(text.splitlines())
    if parsed is None:
        return ()
    headers, rows = parsed
    return (PlaybookTableBlock(title="规则", headers=headers, rows=rows),)
