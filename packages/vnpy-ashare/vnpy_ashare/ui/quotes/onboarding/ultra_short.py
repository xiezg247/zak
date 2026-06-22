"""新用户极致短线 onboarding 引导。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences.onboarding import (
    load_ultra_short_onboarding_done,
    save_ultra_short_onboarding_done,
)
from vnpy_ashare.config.preferences.strategy_profile import (
    StrategyProfileId,
    load_strategy_profile_id,
)
from vnpy_ashare.ui.quotes._host_widget import as_qwidget
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_common.ui.feedback import page_notify

_prompted_pages: set[int] = set()


class UltraShortOnboardingDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("极致短线工作流")
        self.setModal(True)
        self.resize(460, 260)

        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("是否切换到「极致短线」工作流？")
        title.setWordWrap(True)
        layout.addWidget(title)

        body = QtWidgets.QLabel(
            "将自动：\n"
            "· 信号策略切换为打板（AshareLimitBoardStrategy）\n"
            "· 应用盘中布局预设（信号区展开、分组 Tab 显示全部自选）\n\n"
            "之后可在信号区 Profile 下拉中随时改回其他风格。"
        )
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QtWidgets.QDialogButtonBox()
        accept_btn = buttons.addButton("一键切换", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        later_btn = buttons.addButton("稍后再说", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        accept_btn.clicked.connect(self.accept)
        later_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)


def maybe_show_ultra_short_onboarding(page: WatchlistHost) -> None:
    """自选页首次激活时提示切换极致短线 Profile（仅一次）。"""
    if page.page_name != "自选":
        return
    if not page.config.show_watchlist_signals:
        return
    if load_ultra_short_onboarding_done():
        return
    # 仅对仍使用旧默认「中线观察」的用户提示迁移；新默认「短线波段」不再弹窗
    if load_strategy_profile_id() != "medium_watch":
        return
    page_id = id(page)
    if page_id in _prompted_pages:
        return
    _prompted_pages.add(page_id)

    def _show() -> None:
        if load_ultra_short_onboarding_done():
            return
        dialog = UltraShortOnboardingDialog(as_qwidget(page))
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            save_ultra_short_onboarding_done(True)
            return

        profile_id: StrategyProfileId = "ultra_short"
        page.apply_strategy_profile(profile_id)
        save_ultra_short_onboarding_done(True)
        parts = ["已切换为极致短线 Profile"]
        page.status_label.setText(" · ".join(parts))
        page_notify(as_qwidget(page), parts[0], level="success")
        feature = getattr(page, "_watchlist_feature", None)
        if feature is not None:
            feature.apply_layout_preset("intraday")

    QtCore.QTimer.singleShot(600, _show)


def should_offer_ultra_short_onboarding() -> bool:
    return not load_ultra_short_onboarding_done() and load_strategy_profile_id() == "medium_watch"
