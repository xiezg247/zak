"""新用户策略 Profile 首次引导（默认短线放量 short_swing）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.onboarding import (
    load_profile_onboarding_done,
    save_profile_onboarding_done,
)
from vnpy_ashare.config.preferences.strategy_profile import (
    DEFAULT_STRATEGY_PROFILE,
    StrategyProfileId,
    get_strategy_profile,
    list_strategy_profiles,
)
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.features.watchlist.prefs import LayoutPresetId
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_common.ui.feedback import page_notify

_prompted_pages: set[int] = set()

_PROFILE_LAYOUT: dict[StrategyProfileId, LayoutPresetId] = {
    "ultra_short": "intraday",
    "short_swing": "intraday",
    "medium_watch": "review",
    "trend": "review",
}


class ProfileOnboardingDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择交易风格")
        self.setModal(True)
        self.resize(480, 320)

        layout = QtWidgets.QVBoxLayout(self)
        default_spec = get_strategy_profile(DEFAULT_STRATEGY_PROFILE)
        title = QtWidgets.QLabel(f"请选择默认策略 Profile（推荐「{default_spec.title}」· 短线放量突破，可随时在信号区切换）")
        title.setWordWrap(True)
        layout.addWidget(title)

        self._button_group = QtWidgets.QButtonGroup(self)
        profile_layout = QtWidgets.QVBoxLayout()
        for index, spec in enumerate(list_strategy_profiles()):
            hint = f" — {spec.transition_hint}" if spec.transition_hint else ""
            radio = QtWidgets.QRadioButton(f"{spec.title}{hint}")
            radio.setProperty("profile_id", spec.profile_id)
            self._button_group.addButton(radio, index)
            profile_layout.addWidget(radio)
            if spec.profile_id == DEFAULT_STRATEGY_PROFILE:
                radio.setChecked(True)
        layout.addLayout(profile_layout)

        note = QtWidgets.QLabel("确认后将同步信号策略（默认 AshareShortBreakoutStrategy）、硬过滤模板与布局预设。")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        layout.addWidget(note)

        buttons = QtWidgets.QDialogButtonBox()
        accept_btn = buttons.addButton("确认", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        default_label = get_strategy_profile(DEFAULT_STRATEGY_PROFILE).title
        later_btn = buttons.addButton(f"使用默认（{default_label}）", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        accept_btn.clicked.connect(self.accept)
        later_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def selected_profile_id(self) -> StrategyProfileId:
        checked = self._button_group.checkedButton()
        if checked is not None:
            profile_id = checked.property("profile_id")
            if isinstance(profile_id, str) and profile_id in _PROFILE_LAYOUT:
                return profile_id
        return DEFAULT_STRATEGY_PROFILE


def layout_preset_for_profile(profile_id: StrategyProfileId) -> LayoutPresetId:
    return _PROFILE_LAYOUT.get(profile_id, "intraday")


def apply_profile_onboarding(page: WatchlistHost, profile_id: StrategyProfileId) -> None:
    page.apply_strategy_profile(profile_id)
    preset = layout_preset_for_profile(profile_id)
    feature = getattr(page, "_watchlist_feature", None)
    if feature is not None:
        feature.apply_layout_preset(preset)
    title = next((item.title for item in list_strategy_profiles() if item.profile_id == profile_id), profile_id)
    message = f"已应用「{title}」Profile"
    page.status_label.setText(message)
    page_notify(as_qwidget(page), message, level="success")


def maybe_show_profile_onboarding(page: WatchlistHost) -> None:
    """自选页首次激活时引导选择策略 Profile（仅一次）。"""
    if page.page_name != "自选":
        return
    if not page.config.show_watchlist_signals:
        return
    if load_profile_onboarding_done():
        return
    page_id = id(page)
    if page_id in _prompted_pages:
        return
    _prompted_pages.add(page_id)

    def _show() -> None:
        if load_profile_onboarding_done():
            return
        dialog = ProfileOnboardingDialog(as_qwidget(page))
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            profile_id = dialog.selected_profile_id()
        else:
            profile_id = DEFAULT_STRATEGY_PROFILE
        apply_profile_onboarding(page, profile_id)
        save_profile_onboarding_done(True)

    QtCore.QTimer.singleShot(600, _show)


def should_offer_profile_onboarding() -> bool:
    return not load_profile_onboarding_done()


def maybe_show_ultra_short_onboarding(page: WatchlistHost) -> None:
    maybe_show_profile_onboarding(page)


def should_offer_ultra_short_onboarding() -> bool:
    return should_offer_profile_onboarding()
