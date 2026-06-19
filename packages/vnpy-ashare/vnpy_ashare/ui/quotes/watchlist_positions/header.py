"""自选持仓区表头（Profile / 跟随信号 / 操作按钮 / 折叠）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from strategies.registry import get_strategy_meta
from vnpy_ashare.config.preferences.strategy_profile import list_strategy_profiles, load_strategy_profile_id
from vnpy_ashare.config.preferences.watchlist_position import (
    POSITION_PANEL_COLLAPSED_HEIGHT,
    POSITION_PANEL_DEFAULT_HEIGHT,
    WatchlistPositionConfig,
    load_position_panel_enabled,
    load_position_panel_expanded,
    save_position_panel_enabled,
    save_position_panel_expanded,
)
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost


class PositionPanelHeader(QtWidgets.QWidget):
    """持仓区表头：折叠、启用、Profile、策略参数、操作按钮。"""

    config_changed = QtCore.Signal()
    enabled_changed = QtCore.Signal(bool)
    expansion_changed = QtCore.Signal(bool)
    refresh_requested = QtCore.Signal()
    edit_requested = QtCore.Signal()
    remove_requested = QtCore.Signal()
    clear_requested = QtCore.Signal()
    plan_requested = QtCore.Signal()
    journal_requested = QtCore.Signal()
    risk_requested = QtCore.Signal()

    def __init__(self, page: WatchlistHost, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self._building = False
        self._expanded = load_position_panel_expanded()
        self._build_ui()

    # ── 公开 API ──────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._toggle.isChecked()

    def is_expanded(self) -> bool:
        return self._expanded

    def minimum_panel_height(self) -> int:
        return POSITION_PANEL_DEFAULT_HEIGHT if self._expanded else POSITION_PANEL_COLLAPSED_HEIGHT

    def read_config(self) -> WatchlistPositionConfig:
        fast = int(self._fast_spin.value())
        slow = int(self._slow_spin.value())
        if slow <= fast:
            slow = fast + 1
            self._slow_spin.blockSignals(True)
            self._slow_spin.setValue(slow)
            self._slow_spin.blockSignals(False)
        return WatchlistPositionConfig(
            follow_signal=self._follow_check.isChecked(),
            class_name=self._page.position_config.class_name,
            fast_window=fast,
            slow_window=slow,
        ).normalized()

    def apply_config(self, config: WatchlistPositionConfig) -> None:
        item = config.normalized()
        self._follow_check.blockSignals(True)
        self._fast_spin.blockSignals(True)
        self._slow_spin.blockSignals(True)
        self._follow_check.setChecked(item.follow_signal)
        self._fast_spin.setValue(item.fast_window)
        self._slow_spin.setValue(item.slow_window)
        self._follow_check.blockSignals(False)
        self._fast_spin.blockSignals(False)
        self._slow_spin.blockSignals(False)
        self._sync_strategy_controls(
            signal_config=self._page.signal_config if item.follow_signal else None,
        )

    def sync_strategy_profile_combo(self, profile_id: str) -> None:
        self._profile_combo.blockSignals(True)
        index = self._profile_combo.findData(profile_id)
        if index >= 0:
            self._profile_combo.setCurrentIndex(index)
        self._profile_combo.blockSignals(False)

    def sync_follow_display(self, signal_config: WatchlistSignalConfig) -> None:
        if not self._follow_check.isChecked():
            return
        self._sync_strategy_controls(signal_config=signal_config)

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        save_position_panel_expanded(expanded)
        self._sync_expansion_ui()
        if emit:
            self.expansion_changed.emit(expanded)

    def mark_building(self, building: bool) -> None:
        self._building = building

    def set_body_controls_visible(self, visible: bool) -> None:
        for widget in self._body_controls:
            widget.setVisible(visible)

    # ── UI 构建 ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._collapse_button = QtWidgets.QToolButton(self)
        self._collapse_button.setCheckable(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)

        self._toggle = QtWidgets.QCheckBox("启用持仓", self)
        self._toggle.setChecked(load_position_panel_enabled())
        self._toggle.toggled.connect(self._on_enabled_toggled)

        position_cfg = self._page.position_config.normalized()
        self._follow_check = QtWidgets.QCheckBox("跟随信号区", self)
        self._follow_check.setChecked(position_cfg.follow_signal)
        self._follow_check.toggled.connect(self._on_follow_toggled)

        self._profile_combo = QtWidgets.QComboBox(self)
        self._profile_combo.setObjectName("StrategyProfileCombo")
        self._profile_combo.setMinimumWidth(96)
        self._profile_combo.setToolTip("策略 Profile（与信号区同步）")
        for spec in list_strategy_profiles():
            self._profile_combo.addItem(spec.title, spec.profile_id)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.sync_strategy_profile_combo(load_strategy_profile_id())

        self._strategy_label = QtWidgets.QLabel("", self)
        self._strategy_label.setObjectName("SectionLabel")

        self._fast_spin = QtWidgets.QSpinBox(self)
        self._fast_spin.setRange(2, 60)
        self._fast_spin.setPrefix("快 ")
        self._fast_spin.setValue(position_cfg.fast_window)

        self._slow_spin = QtWidgets.QSpinBox(self)
        self._slow_spin.setRange(3, 120)
        self._slow_spin.setPrefix("慢 ")
        self._slow_spin.setValue(position_cfg.slow_window)

        self._edit_button = QtWidgets.QPushButton("编辑", self)
        self._edit_button.setObjectName("SecondaryButton")
        self._edit_button.clicked.connect(self.edit_requested.emit)

        self._remove_button = QtWidgets.QPushButton("移出", self)
        self._remove_button.setObjectName("SecondaryButton")
        self._remove_button.clicked.connect(self.remove_requested.emit)

        self._clear_button = QtWidgets.QPushButton("清空", self)
        self._clear_button.setObjectName("SecondaryButton")
        self._clear_button.clicked.connect(self.clear_requested.emit)

        self._refresh_button = QtWidgets.QPushButton("刷新", self)
        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.clicked.connect(self.refresh_requested.emit)

        self._plan_button = QtWidgets.QPushButton("今日计划", self)
        self._plan_button.setObjectName("SecondaryButton")
        self._plan_button.setToolTip("查看/编辑当日交易计划（计划外登记将标记 off_plan）")
        self._plan_button.clicked.connect(self.plan_requested.emit)

        self._journal_button = QtWidgets.QPushButton("复盘", self)
        self._journal_button.setObjectName("SecondaryButton")
        self._journal_button.setToolTip("近 7 日流水胜率、盈亏比与违规统计")
        self._journal_button.clicked.connect(self.journal_requested.emit)

        self._risk_button = QtWidgets.QPushButton("风控设置", self)
        self._risk_button.setObjectName("SecondaryButton")
        self._risk_button.setToolTip("总资金、单笔风险与风控闸阈值")
        self._risk_button.clicked.connect(self.risk_requested.emit)

        layout.addWidget(self._collapse_button)
        layout.addWidget(QtWidgets.QLabel("持仓策略", self))
        layout.addWidget(self._toggle)
        layout.addStretch()
        layout.addWidget(self._profile_combo)
        layout.addWidget(self._follow_check)
        layout.addWidget(self._strategy_label)
        layout.addWidget(self._fast_spin)
        layout.addWidget(self._slow_spin)
        layout.addWidget(self._edit_button)
        layout.addWidget(self._remove_button)
        layout.addWidget(self._clear_button)
        layout.addWidget(self._refresh_button)
        layout.addWidget(self._plan_button)
        layout.addWidget(self._journal_button)
        layout.addWidget(self._risk_button)

        self._fast_spin.valueChanged.connect(self._emit_config_changed)
        self._slow_spin.valueChanged.connect(self._emit_config_changed)

        self._body_controls = (
            self._toggle,
            self._follow_check,
            self._strategy_label,
            self._fast_spin,
            self._slow_spin,
            self._edit_button,
            self._remove_button,
            self._clear_button,
            self._refresh_button,
        )
        self._sync_strategy_controls(signal_config=self._page.signal_config)
        self._sync_expansion_ui()

    # ── 事件处理 ────────────────────────────────────────────

    def _on_profile_changed(self, _index: int) -> None:
        profile_id = str(self._profile_combo.currentData() or "")
        if not profile_id:
            return
        self._page.apply_strategy_profile(profile_id)

    def _on_follow_toggled(self, _checked: bool) -> None:
        self._sync_strategy_controls(signal_config=self._page.signal_config)
        self._emit_config_changed()

    def _on_enabled_toggled(self, checked: bool) -> None:
        save_position_panel_enabled(checked)
        self.enabled_changed.emit(checked)

    def _on_collapse_toggled(self, checked: bool) -> None:
        self.set_expanded(checked)

    def _strategy_title(self, class_name: str) -> str:
        meta = get_strategy_meta(class_name)
        return meta.title if meta is not None else class_name

    def _sync_strategy_controls(self, signal_config: WatchlistSignalConfig | None = None) -> None:
        follow = self._follow_check.isChecked()
        if follow:
            cfg = (signal_config or self._page.signal_config).normalized()
            self._strategy_label.setText(f"跟随·{self._strategy_title(cfg.class_name)}")
            self._strategy_label.setVisible(True)
            self._fast_spin.setVisible(False)
            self._slow_spin.setVisible(False)
            return
        item = self._page.position_config.normalized()
        self._strategy_label.setText(self._strategy_title(item.class_name))
        self._strategy_label.setVisible(True)
        self._fast_spin.setVisible(True)
        self._slow_spin.setVisible(True)
        self._fast_spin.setEnabled(True)
        self._slow_spin.setEnabled(True)

    def _sync_expansion_ui(self) -> None:
        expanded = self._expanded
        self._collapse_button.setChecked(expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow)
        for widget in self._body_controls:
            widget.setVisible(expanded)

    def _emit_config_changed(self) -> None:
        if self._building:
            return
        self.config_changed.emit()
