"""自选页工具栏随工作流预设显隐。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId
from vnpy_ashare.ui.quotes.features.watchlist.preset_specs import PRESET_SPECS
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost

_EMOTION_MORE_LABEL = "情绪周期"
_RISK_MORE_LABEL = "风控状态"


def _set_more_menu_action_visible(page: WatchlistHost, label: str, visible: bool) -> None:
    actions = getattr(page, "_more_menu_actions", None)
    if not isinstance(actions, dict):
        return
    action = actions.get(label)
    if action is not None:
        action.setVisible(visible)


def _sync_emotion_risk_chips(page: WatchlistHost, *, show_in_toolbar: bool) -> None:
    emotion = getattr(page, "emotion_cycle_chip", None)
    risk = getattr(page, "risk_gate_chip", None)
    if emotion is not None:
        emotion.setVisible(show_in_toolbar)
    if risk is not None:
        risk.setVisible(show_in_toolbar)
    _set_more_menu_action_visible(page, _EMOTION_MORE_LABEL, not show_in_toolbar)
    _set_more_menu_action_visible(page, _RISK_MORE_LABEL, not show_in_toolbar)


def create_emotion_risk_more_buttons(page: WatchlistHost) -> list[tuple[str, QtWidgets.QPushButton]]:
    """创建供「更多」菜单调用的情绪/风控代理按钮（默认隐藏，由预设切换显隐）。"""
    if not (page.config.show_watchlist_signals or page.config.show_watchlist_positions):
        return []

    emotion_btn = QtWidgets.QPushButton(as_qwidget(page))
    emotion_btn.hide()

    def _show_emotion_status() -> None:
        chip = getattr(page, "emotion_cycle_chip", None)
        text = chip.toolTip() if chip is not None else ""
        QtWidgets.QMessageBox.information(
            as_qwidget(page),
            _EMOTION_MORE_LABEL,
            text or "暂无市场广度数据",
        )

    emotion_btn.clicked.connect(_show_emotion_status)

    risk_btn = QtWidgets.QPushButton(as_qwidget(page))
    risk_btn.hide()
    risk_btn.clicked.connect(page._open_risk_settings)
    page.emotion_cycle_more_button = emotion_btn
    page.risk_gate_more_button = risk_btn
    return [
        (_EMOTION_MORE_LABEL, emotion_btn),
        (_RISK_MORE_LABEL, risk_btn),
    ]


def apply_toolbar_for_preset(page: WatchlistHost, preset_id: LayoutPresetId) -> None:
    spec = PRESET_SPECS[preset_id]
    if getattr(page, "_watchlist_feature", None) is not None:
        _sync_emotion_risk_chips(page, show_in_toolbar=False)
        _set_more_menu_action_visible(page, _EMOTION_MORE_LABEL, spec.show_emotion_risk_chips)
        _set_more_menu_action_visible(page, _RISK_MORE_LABEL, spec.show_emotion_risk_chips)
        return

    register = getattr(page, "register_position_button", None)
    if register is not None and page.config.show_watchlist_positions:
        register.setVisible(spec.show_register_toolbar)
    add_signal = getattr(page, "add_signal_panel_button", None)
    if add_signal is not None and page.config.show_watchlist_signals:
        add_signal.setVisible(spec.show_add_signal_toolbar)
    _sync_emotion_risk_chips(page, show_in_toolbar=spec.show_emotion_risk_chips)
