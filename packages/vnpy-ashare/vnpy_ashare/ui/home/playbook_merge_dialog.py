"""Profile 切换时 Playbook 模板合并确认。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.config.preferences.strategy_profile import StrategyProfileId, get_strategy_profile
from vnpy_ashare.services.trading_playbook import list_playbook_sections


def prompt_playbook_template_merge(
    parent: QtWidgets.QWidget,
    *,
    from_profile_id: StrategyProfileId,
    to_profile_id: StrategyProfileId,
    section_ids: tuple[str, ...],
) -> bool:
    """询问是否将仍为旧模板默认内容的章节套用新 Profile 模板。"""
    if not section_ids:
        return False

    from_title = get_strategy_profile(from_profile_id).title
    to_title = get_strategy_profile(to_profile_id).title
    titles = {item.section_id: item.title for item in list_playbook_sections()}
    names = "\n".join(f"  · {titles.get(sid, sid)}" for sid in section_ids)

    answer = QtWidgets.QMessageBox.question(
        parent,
        "更新守则模板",
        (f"以下章节仍为「{from_title}」默认模板，是否套用「{to_title}」对应章节？\n\n{names}\n\n已手动编辑过的章节不会改动。"),
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        QtWidgets.QMessageBox.StandardButton.No,
    )
    return answer == QtWidgets.QMessageBox.StandardButton.Yes
