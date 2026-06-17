"""退潮期批量入自选软拦截（T-06）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets


def is_emotion_recession() -> bool:
    from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot

    cycle = load_emotion_cycle_snapshot()
    return cycle is not None and cycle.stage == "recession"


def confirm_recession_batch_watchlist(parent: QtWidgets.QWidget | None = None) -> bool:
    """退潮期批量加自选前确认；非退潮直接放行。"""
    if not is_emotion_recession():
        return True
    answer = QtWidgets.QMessageBox.question(
        parent,
        "退潮期提示",
        "当前情绪阶段为退潮，建议改用「情绪观察」配方（R-04）或保持空仓。\n\n仍要批量加入自选吗？",
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        QtWidgets.QMessageBox.StandardButton.No,
    )
    return answer == QtWidgets.QMessageBox.StandardButton.Yes
