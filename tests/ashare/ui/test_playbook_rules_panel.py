"""Playbook 规则面板测试。"""

from vnpy_ashare.config.playbook_templates.defaults import (
    _COMMON_DISCIPLINE,
    _COMMON_RISK,
    _ULTRA_SHORT_TIMING,
    _ULTRA_SHORT_UNIVERSE,
)
from vnpy_ashare.ui.home.playbook_markdown_tables import parse_playbook_table_blocks
from vnpy_ashare.ui.home.playbook_rules_panel import extract_playbook_note_lines


def test_parse_ultra_short_timing_table() -> None:
    blocks = parse_playbook_table_blocks(_ULTRA_SHORT_TIMING)
    assert len(blocks) == 1
    assert blocks[0].title == "五阶段情绪 · 做不做"
    assert len(blocks[0].rows) == 5


def test_parse_universe_and_risk_tables() -> None:
    universe = parse_playbook_table_blocks(_ULTRA_SHORT_UNIVERSE)
    assert len(universe) == 1
    assert universe[0].headers == ("维度", "规则")

    risk = parse_playbook_table_blocks(_COMMON_RISK)
    assert len(risk) == 1
    assert risk[0].title == "仓位与风控"

    discipline = parse_playbook_table_blocks(_COMMON_DISCIPLINE)
    assert len(discipline) == 1
    assert len(discipline[0].rows) == 5


def test_extract_timing_note() -> None:
    note = extract_playbook_note_lines(_ULTRA_SHORT_TIMING)
    assert "1 万亿" in note
