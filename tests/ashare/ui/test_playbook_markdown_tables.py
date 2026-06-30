"""Playbook Markdown 表格解析测试。"""

from vnpy_ashare.config.playbook_templates.defaults import _ULTRA_SHORT_EXECUTION
from vnpy_ashare.ui.home.playbook_markdown_tables import parse_playbook_table_blocks


def test_parse_ultra_short_execution_tables() -> None:
    blocks = parse_playbook_table_blocks(_ULTRA_SHORT_EXECUTION)
    assert len(blocks) == 2
    assert blocks[0].title == "三类买点"
    assert blocks[0].headers == ("模式", "环境", "规则要点")
    assert len(blocks[0].rows) == 3
    assert blocks[1].title == "隔日卖点铁则"
    assert blocks[1].headers == ("类型", "条件", "动作")
    assert len(blocks[1].rows) == 5


def test_parse_empty_markdown() -> None:
    assert parse_playbook_table_blocks("") == ()
