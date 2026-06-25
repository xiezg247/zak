"""选股左栏可折叠配置分组。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.config.preferences._settings import (
    coerce_settings_bool,
    read_migrated_value,
    write_setting_value,
)
from vnpy_common.paths import QSETTINGS_ORG
from vnpy_common.ui.theme.manager import theme_manager

_LEGACY_SCREENER_UI = "screener_ui"


def _settings_key(section_id: str) -> str:
    return f"screener/config_section_{section_id}_expanded"


def _legacy_settings_key(section_id: str) -> str:
    return f"config_section_{section_id}_expanded"


def load_config_section_expanded(section_id: str, default: bool) -> bool:
    key = _settings_key(section_id)
    legacy = ((QSETTINGS_ORG, _LEGACY_SCREENER_UI, _legacy_settings_key(section_id)),)
    raw = read_migrated_value(key, legacy, default)
    return coerce_settings_bool(raw, default=default)


def save_config_section_expanded(section_id: str, expanded: bool) -> None:
    write_setting_value(_settings_key(section_id), expanded)


class ScreenerConfigSection(QtWidgets.QWidget):
    """左栏 Accordion 分组：标题行 + 可折叠内容区。"""

    expansion_changed = QtCore.Signal(bool)

    def __init__(
        self,
        title: str,
        *,
        section_id: str,
        expanded: bool = True,
        persist: bool = True,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerConfigSection")
        self._section_id = section_id
        self._persist = persist
        self._content_widget: QtWidgets.QWidget | None = None

        initial_expanded = load_config_section_expanded(section_id, expanded) if persist else expanded
        self._expanded = initial_expanded
        self._build_ui(title)
        theme_manager().bind_stylesheet(self)
        self.set_expanded(initial_expanded, emit=False, persist=False)

    def _build_ui(self, title: str) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 4)
        root.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self._collapse_button = QtWidgets.QToolButton(self)
        self._collapse_button.setObjectName("ScreenerConfigSectionToggle")
        self._collapse_button.setCheckable(True)
        self._collapse_button.clicked.connect(self._on_collapse_toggled)
        header.addWidget(self._collapse_button)

        self._title_label = QtWidgets.QLabel(title)
        self._title_label.setObjectName("ScreenerSectionLabel")
        header.addWidget(self._title_label)
        header.addStretch()
        root.addLayout(header)

        self._content_host = QtWidgets.QWidget(self)
        self._content_host.setObjectName("ScreenerConfigSectionContent")
        self._content_layout = QtWidgets.QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        root.addWidget(self._content_host)

    def content_layout(self) -> QtWidgets.QVBoxLayout:
        return self._content_layout

    def set_content(self, widget: QtWidgets.QWidget) -> None:
        if self._content_widget is not None:
            self._content_layout.removeWidget(self._content_widget)
            self._content_widget.setParent(None)
        self._content_widget = widget
        self._content_layout.addWidget(widget)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True, persist: bool | None = None) -> None:
        changed = self._expanded != expanded
        self._expanded = expanded
        self._sync_collapse_button()
        self._content_host.setVisible(expanded)
        should_persist = self._persist if persist is None else persist
        if should_persist and changed:
            save_config_section_expanded(self._section_id, expanded)
        if emit and changed:
            self.expansion_changed.emit(expanded)

    def expand(self) -> None:
        self.set_expanded(True)

    def collapse(self) -> None:
        self.set_expanded(False)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(QtCore.Qt.ArrowType.DownArrow if self._expanded else QtCore.Qt.ArrowType.RightArrow)
        self._collapse_button.blockSignals(False)

    def _on_collapse_toggled(self, expanded: bool) -> None:
        self.set_expanded(expanded)