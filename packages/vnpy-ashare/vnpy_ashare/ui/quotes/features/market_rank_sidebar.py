"""市场页榜单侧栏（可折叠）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.rank_catalog import iter_rank_sidebar_rows
from vnpy_common.ui.theme import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

RANK_SIDEBAR_EXPANDED_KEY = "quotes/market/rank_sidebar_expanded_v1"
RANK_SIDEBAR_EXPANDED_WIDTH = 116
RANK_SIDEBAR_HANDLE_WIDTH = 24
RANK_SIDEBAR_COLLAPSED_WIDTH = RANK_SIDEBAR_HANDLE_WIDTH
COLLAPSE_BUTTON_SIZE = 20
RANK_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole


def load_rank_sidebar_expanded(*, default: bool = True) -> bool:
    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    value = settings.value(RANK_SIDEBAR_EXPANDED_KEY)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def save_rank_sidebar_expanded(expanded: bool) -> None:
    settings = QtCore.QSettings("vnpy_ashare", "ZakTerminal")
    settings.setValue(RANK_SIDEBAR_EXPANDED_KEY, expanded)


def rank_sidebar_collapse_arrow(expanded: bool) -> QtCore.Qt.ArrowType:
    """左栏右缘按钮：展开时向左收起，折叠时向右展开。"""
    return QtCore.Qt.ArrowType.LeftArrow if expanded else QtCore.Qt.ArrowType.RightArrow


def populate_rank_sidebar_list(rank_list: QtWidgets.QListWidget) -> None:
    rank_list.clear()
    for group_title, spec in iter_rank_sidebar_rows():
        if spec is None:
            header = QtWidgets.QListWidgetItem(group_title)
            header.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            header.setData(RANK_ID_ROLE, "")
            font = rank_list.font()
            header_font = QtGui.QFont(font)
            if header_font.pointSize() > 0:
                header_font.setPointSize(max(header_font.pointSize() - 1, 8))
            header_font.setBold(True)
            header.setFont(header_font)
            rank_list.addItem(header)
            continue
        item = QtWidgets.QListWidgetItem(spec.title)
        item.setData(RANK_ID_ROLE, spec.id)
        rank_list.addItem(item)


def rank_id_from_sidebar_row(rank_list: QtWidgets.QListWidget, row: int) -> str:
    item = rank_list.item(row)
    if item is None:
        return ""
    return str(item.data(RANK_ID_ROLE) or "").strip()


class MarketRankSidebar(QtWidgets.QWidget):
    """榜单列表 + 右缘折叠钮。"""

    expansion_changed = QtCore.Signal(bool)

    def __init__(self, page: QuotesPage, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self._expanded = load_rank_sidebar_expanded()

        self.setObjectName("MarketRankSidebar")
        theme_manager().bind_stylesheet(self)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._body = QtWidgets.QWidget(self)
        self._body.setObjectName("MarketRankSidebarBody")
        body_layout = QtWidgets.QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        rank_title = QtWidgets.QLabel("榜单")
        rank_title.setObjectName("MarketRankSidebarTitle")
        body_layout.addWidget(rank_title)

        self.rank_list = QtWidgets.QListWidget(self._body)
        self.rank_list.setObjectName("RankSidebar")
        populate_rank_sidebar_list(self.rank_list)
        body_layout.addWidget(self.rank_list, stretch=1)

        handle = QtWidgets.QWidget(self)
        handle.setObjectName("MarketRankSidebarHandle")
        handle.setFixedWidth(RANK_SIDEBAR_HANDLE_WIDTH)
        handle_layout = QtWidgets.QVBoxLayout(handle)
        handle_layout.setContentsMargins(0, 0, 0, 0)
        handle_layout.setSpacing(0)

        self._collapse_button = QtWidgets.QToolButton(handle)
        self._collapse_button.setObjectName("MarketRankSidebarCollapseButton")
        self._collapse_button.setCheckable(True)
        self._collapse_button.setAutoRaise(True)
        self._collapse_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._collapse_button.setFixedSize(COLLAPSE_BUTTON_SIZE, COLLAPSE_BUTTON_SIZE)
        self._collapse_button.setToolTip("收起榜单")
        self._collapse_button.clicked.connect(self._on_collapse_toggled)

        handle_layout.addStretch(1)
        handle_layout.addWidget(
            self._collapse_button,
            alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
        )
        handle_layout.addStretch(1)

        root.addWidget(self._body, stretch=1)
        root.addWidget(handle)

        self._apply_expanded(self._expanded, emit=False)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, *, emit: bool = True) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        save_rank_sidebar_expanded(expanded)
        self._apply_expanded(expanded, emit=emit)

    def _on_collapse_toggled(self, expanded: bool) -> None:
        self.set_expanded(expanded)

    def _sync_collapse_button(self) -> None:
        self._collapse_button.blockSignals(True)
        self._collapse_button.setChecked(self._expanded)
        self._collapse_button.setArrowType(rank_sidebar_collapse_arrow(self._expanded))
        self._collapse_button.setToolTip("收起榜单" if self._expanded else "展开榜单")
        self._collapse_button.blockSignals(False)

    def _apply_expanded(self, expanded: bool, *, emit: bool) -> None:
        self._sync_collapse_button()
        self._body.setVisible(expanded)
        if expanded:
            self.setMinimumWidth(RANK_SIDEBAR_EXPANDED_WIDTH)
            self.setMaximumWidth(RANK_SIDEBAR_EXPANDED_WIDTH)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        else:
            self.setMinimumWidth(RANK_SIDEBAR_COLLAPSED_WIDTH)
            self.setMaximumWidth(RANK_SIDEBAR_COLLAPSED_WIDTH)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        self.updateGeometry()
        if emit:
            self.expansion_changed.emit(expanded)


def sync_rank_splitter_for_expansion(page: QuotesPage, expanded: bool) -> None:
    """折叠时收窄 splitter 左侧整栏，仅保留折叠钮。"""
    sidebar = getattr(page, "rank_sidebar", None)
    splitter = getattr(page, "_rank_splitter", None)
    if sidebar is None or splitter is None or splitter.count() < 2:
        return

    if expanded:
        sidebar.setMinimumWidth(RANK_SIDEBAR_EXPANDED_WIDTH)
        sidebar.setMaximumWidth(RANK_SIDEBAR_EXPANDED_WIDTH)
        saved = getattr(page, "_rank_splitter_saved_state", None)
        if isinstance(saved, QtCore.QByteArray) and not saved.isEmpty():
            splitter.restoreState(saved)
        return

    state = splitter.saveState()
    if isinstance(state, QtCore.QByteArray) and not state.isEmpty():
        page._rank_splitter_saved_state = state

    sidebar.setMinimumWidth(RANK_SIDEBAR_COLLAPSED_WIDTH)
    sidebar.setMaximumWidth(RANK_SIDEBAR_COLLAPSED_WIDTH)
    sizes = splitter.sizes()
    total = max(sum(sizes), splitter.width(), RANK_SIDEBAR_EXPANDED_WIDTH + 200)
    splitter.blockSignals(True)
    splitter.setSizes([RANK_SIDEBAR_COLLAPSED_WIDTH, total - RANK_SIDEBAR_COLLAPSED_WIDTH])
    splitter.blockSignals(False)
