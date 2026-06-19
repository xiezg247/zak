"""自选信号区表头（Profile/策略/参数/按钮/折叠）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from strategies.registry import list_signal_strategy_metas
from strategies.signals import STRATEGY_SIGNAL_DEFAULTS
from vnpy_ashare.config.preferences.signal_panel_columns import (
    SIGNAL_PANEL_OPTIONAL_COLUMNS,
    normalize_visible_optional_keys,
)
from vnpy_ashare.config.preferences.strategy_profile import (
    list_strategy_profiles,
    load_strategy_profile_id,
    match_strategy_profile,
    save_strategy_profile_id,
)
from vnpy_ashare.config.preferences.watchlist_signal import (
    DEFAULT_CLASS,
    WatchlistSignalConfig,
    load_signal_panel_columns,
    load_signal_panel_enabled,
    load_signal_panel_expanded,
    save_signal_panel_columns,
    save_signal_panel_enabled,
    save_signal_panel_expanded,
)
from vnpy_ashare.ui.quotes.watchlist.host import WatchlistHost
from vnpy_ashare.ui.quotes.watchlist_signals.splitter import (
    SIGNAL_PANEL_COLLAPSED_HEIGHT,
)


class SignalPanelHeader(QtWidgets.QWidget):
    """信号区表头行：折叠、Profile、策略、参数、操作按钮。"""

    config_changed = QtCore.Signal()
    refresh_requested = QtCore.Signal()
    ai_scan_requested = QtCore.Signal()
    ai_clicked = QtCore.Signal()
    register_position_clicked = QtCore.Signal()
    remove_requested = QtCore.Signal()
    clear_requested = QtCore.Signal()
    enabled_changed = QtCore.Signal(bool)
    expansion_changed = QtCore.Signal(bool)

    def __init__(self, page: WatchlistHost, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self._building = False
        self._column_menu: QtWidgets.QMenu | None = None
        self._body_widgets: list[QtWidgets.QWidget] = []
        self._expanded = load_signal_panel_expanded()
        self._build_ui()

    # ── public ──────────────────────────────────────────────

    def read_config(self) -> WatchlistSignalConfig:
        fast = int(self._fast_spin.value())
        slow = int(self._slow_spin.value())
        if slow <= fast:
            slow = fast + 1
            self._slow_spin.blockSignals(True)
            self._slow_spin.setValue(slow)
            self._slow_spin.blockSignals(False)
        class_name = str(self._strategy_combo.currentData() or DEFAULT_CLASS)
        return WatchlistSignalConfig(
            class_name=class_name,
            fast_window=fast,
            slow_window=slow,
        ).normalized()

    def apply_config(self, config: WatchlistSignalConfig) -> None:
        item = config.normalized()
        self._strategy_combo.blockSignals(True)
        self._fast_spin.blockSignals(True)
        self._slow_spin.blockSignals(True)
        index = self._strategy_combo.findData(item.class_name)
        if index >= 0:
            self._strategy_combo.setCurrentIndex(index)
        self._fast_spin.setValue(item.fast_window)
        self._slow_spin.setValue(item.slow_window)
        self._strategy_combo.blockSignals(False)
        self._fast_spin.blockSignals(False)
        self._slow_spin.blockSignals(False)

    def sync_strategy_profile_combo(self, profile_id: str) -> None:
        self._profile_combo.blockSignals(True)
        index = self._profile_combo.findData(profile_id)
        if index >= 0:
            self._profile_combo.setCurrentIndex(index)
        self._profile_combo.blockSignals(False)

    def is_enabled(self) -> bool:
        return self._toggle.isChecked()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        changed = self._expanded != expanded
        self._expanded = expanded
        self._apply_expanded(expanded, emit=emit and changed)

    def sync_splitter_geometry(self) -> None:
        """供 splitter 布局前同步 min/max，避免 QSplitter 忽略目标高度。"""
        self._apply_expanded(self._expanded, emit=False)

    def show_column_menu(self) -> None:
        menu = self._column_menu
        if menu is None:
            menu = QtWidgets.QMenu(self)
            self._column_menu = menu
            for key, label in SIGNAL_PANEL_OPTIONAL_COLUMNS:
                action = menu.addAction(label)
                action.setCheckable(True)
                action.setData(key)
                action.triggered.connect(self._on_column_toggled)
        visible = set(load_signal_panel_columns())
        for action in menu.actions():
            key = str(action.data() or "")
            action.blockSignals(True)
            action.setChecked(key in visible)
            action.blockSignals(False)
        menu.exec(self._column_button.mapToGlobal(self._column_button.rect().bottomLeft()))

    def visible_column_keys(self) -> list[str]:
        return list(load_signal_panel_columns())

    def controls(self) -> tuple[QtWidgets.QWidget, ...]:
        """返回子控件列表，供 expansion/enabled 切换可见性。"""
        return tuple(self._body_widgets)

    def set_controls_visible(self, visible: bool) -> None:
        for widget in self._body_widgets:
            widget.setVisible(visible)

    def set_controls_enabled(self, enabled: bool) -> None:
        for widget in self._body_widgets:
            widget.setEnabled(enabled)

    def mark_building(self, building: bool) -> None:
        self._building = building

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

        self._profile_combo = QtWidgets.QComboBox(self)
        self._profile_combo.setObjectName("StrategyProfileCombo")
        self._profile_combo.setMinimumWidth(96)
        self._profile_combo.setToolTip("策略 Profile：切换后同步信号策略与参数")
        for spec in list_strategy_profiles():
            self._profile_combo.addItem(spec.title, spec.profile_id)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.sync_strategy_profile_combo(load_strategy_profile_id())

        self._toggle = QtWidgets.QCheckBox("启用信号", self)
        self._toggle.setChecked(load_signal_panel_enabled())
        self._toggle.toggled.connect(self._on_enabled_toggled)

        self._strategy_combo = QtWidgets.QComboBox(self)
        self._strategy_combo.setObjectName("SignalStrategyCombo")
        self._strategy_combo.setMinimumWidth(108)
        for meta in list_signal_strategy_metas():
            self._strategy_combo.addItem(meta.title, meta.class_name)
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)

        self._fast_spin = QtWidgets.QSpinBox(self)
        self._fast_spin.setRange(2, 60)
        self._fast_spin.setPrefix("快 ")
        self._fast_spin.setValue(self._page.signal_config.fast_window)

        self._slow_spin = QtWidgets.QSpinBox(self)
        self._slow_spin.setRange(3, 120)
        self._slow_spin.setPrefix("慢 ")
        self._slow_spin.setValue(self._page.signal_config.slow_window)

        self._register_position_button = QtWidgets.QPushButton("→ 登记持仓", self)
        self._register_position_button.setObjectName("SecondaryButton")
        self._register_position_button.clicked.connect(self._on_register_position_clicked)

        self._remove_button = QtWidgets.QPushButton("移出", self)
        self._remove_button.setObjectName("SecondaryButton")
        self._remove_button.clicked.connect(self.remove_requested.emit)

        self._clear_button = QtWidgets.QPushButton("清空", self)
        self._clear_button.setObjectName("SecondaryButton")
        self._clear_button.clicked.connect(self.clear_requested.emit)

        self._refresh_button = QtWidgets.QPushButton("刷新", self)
        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.clicked.connect(self.refresh_requested.emit)

        self._column_button = QtWidgets.QPushButton("列", self)
        self._column_button.setObjectName("SecondaryButton")
        self._column_button.setToolTip("选择信号区显示列")
        self._column_button.clicked.connect(self.show_column_menu)

        self._ai_button = QtWidgets.QPushButton("AI 解读", self)
        self._ai_button.setObjectName("SecondaryButton")
        self._ai_button.setToolTip("结合信号区快照与双均线工具做研究解读")
        self._ai_button.clicked.connect(self._on_ai_clicked)

        self._ai_scan_button = QtWidgets.QPushButton("AI 扫区", self)
        self._ai_scan_button.setObjectName("SecondaryButton")
        self._ai_scan_button.setToolTip("批量扫描信号区全部监控标的")
        self._ai_scan_button.clicked.connect(self.ai_scan_requested.emit)

        layout.addWidget(self._collapse_button)
        layout.addWidget(QtWidgets.QLabel("策略信号", self))
        layout.addWidget(self._profile_combo)
        layout.addWidget(self._toggle)
        layout.addStretch()
        layout.addWidget(self._strategy_combo)
        layout.addWidget(self._fast_spin)
        layout.addWidget(self._slow_spin)
        layout.addWidget(self._register_position_button)
        layout.addWidget(self._remove_button)
        layout.addWidget(self._clear_button)
        layout.addWidget(self._refresh_button)
        layout.addWidget(self._column_button)
        layout.addWidget(self._ai_button)
        layout.addWidget(self._ai_scan_button)

        self._fast_spin.valueChanged.connect(self._emit_config_changed)
        self._slow_spin.valueChanged.connect(self._emit_config_changed)

        self._body_widgets = [
            self._strategy_combo,
            self._fast_spin,
            self._slow_spin,
            self._register_position_button,
            self._remove_button,
            self._clear_button,
            self._refresh_button,
            self._column_button,
            self._ai_button,
            self._ai_scan_button,
        ]
        self._apply_enabled(self._toggle.isChecked())
        self._apply_expanded(self._expanded, emit=False)

    # ── 事件处理 ────────────────────────────────────────────

    def _on_profile_changed(self, _index: int) -> None:
        profile_id = str(self._profile_combo.currentData() or "")
        if not profile_id:
            return
        self._page.apply_strategy_profile(profile_id)

    def _on_strategy_changed(self, _index: int) -> None:
        class_name = str(self._strategy_combo.currentData() or DEFAULT_CLASS)
        defaults = STRATEGY_SIGNAL_DEFAULTS.get(class_name)
        if defaults is not None:
            fast, slow = defaults
            self._fast_spin.blockSignals(True)
            self._slow_spin.blockSignals(True)
            self._fast_spin.setValue(fast)
            self._slow_spin.setValue(max(slow, fast + 1))
            self._fast_spin.blockSignals(False)
            self._slow_spin.blockSignals(False)
        matched = match_strategy_profile(self.read_config())
        save_strategy_profile_id(matched)
        self.sync_strategy_profile_combo(matched)
        position_panel = getattr(self._page, "position_panel", None)
        if position_panel is not None:
            position_panel.sync_strategy_profile_combo(matched)
        self._emit_config_changed()

    def _on_column_toggled(self, checked: bool) -> None:  # noqa: FBT001
        action = self.sender()
        if not isinstance(action, QtGui.QAction):
            return
        key = str(action.data() or "").strip()
        if not key:
            return
        keys = self.visible_column_keys()
        if checked and key not in keys:
            keys.append(key)
        elif not checked and key in keys:
            keys.remove(key)
        keys = normalize_visible_optional_keys(keys)
        save_signal_panel_columns(keys)
        self.config_changed.emit()

    def _on_enabled_toggled(self, enabled: bool) -> None:
        save_signal_panel_enabled(enabled)
        self._apply_enabled(enabled)
        self.enabled_changed.emit(enabled)

    def _apply_enabled(self, enabled: bool) -> None:
        for widget in self._body_widgets:
            widget.setEnabled(enabled)

    def _on_ai_clicked(self) -> None:
        self.ai_clicked.emit()

    def _on_register_position_clicked(self) -> None:
        self.register_position_clicked.emit()

    def _on_collapse_toggled(self, expanded: bool) -> None:
        save_signal_panel_expanded(expanded)
        self.set_expanded(expanded)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.blockSignals(False)

    def _apply_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        self._sync_collapse_button()
        if expanded:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(0)
        else:
            self.setMinimumHeight(SIGNAL_PANEL_COLLAPSED_HEIGHT)
            self.setMaximumHeight(SIGNAL_PANEL_COLLAPSED_HEIGHT + 4)
        if emit:
            self.expansion_changed.emit(expanded)

    def _emit_config_changed(self) -> None:
        if self._building:
            self._page.apply_signal_panel_config()
            return
        self.config_changed.emit()
