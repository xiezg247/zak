"""市场页榜单侧栏（可折叠）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.rank.rank_catalog import iter_rank_sidebar_rows
from vnpy_common.ui.theme import theme_manager

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage

RANK_SIDEBAR_EXPANDED_KEY = "quotes/market/rank_sidebar_expanded_v1"
RANK_SIDEBAR_EXPANDED_WIDTH = 132
RANK_SIDEBAR_HANDLE_WIDTH = 24
RANK_SIDEBAR_COLLAPSED_WIDTH = RANK_SIDEBAR_HANDLE_WIDTH
COLLAPSE_BUTTON_SIZE = 20
RANK_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole
RANK_ROW_KIND_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1
KIND_GROUP = "group"
KIND_RANK = "rank"
RANK_ITEM_INDENT = 14


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


_ParentIndex = QtCore.QModelIndex | QtCore.QPersistentModelIndex


class RankSidebarDelegate(QtWidgets.QStyledItemDelegate):
    """分组标题与可点榜单项分层绘制，避免二级项与分组混淆。"""

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: _ParentIndex,
    ) -> None:
        kind = index.data(RANK_ROW_KIND_ROLE)
        if kind == KIND_GROUP:
            self._paint_group(painter, option, index)
            return

        opt = QtWidgets.QStyleOptionViewItem(option)
        view_opt = cast(Any, opt)
        view_opt.rect = view_opt.rect.adjusted(RANK_ITEM_INDENT, 0, -4, 0)
        if view_opt.state & QtWidgets.QStyle.StateFlag.State_Selected:
            tokens = theme_manager().tokens()
            accent = QtGui.QColor(tokens.accent)
            bar_rect = QtCore.QRect(
                option.rect.left() + 6,
                option.rect.top() + 5,
                3,
                option.rect.height() - 10,
            )
            painter.fillRect(bar_rect, accent)
        super().paint(painter, opt, index)

    def sizeHint(
        self,
        option: QtWidgets.QStyleOptionViewItem,
        index: _ParentIndex,
    ) -> QtCore.QSize:
        base = super().sizeHint(option, index)
        kind = index.data(RANK_ROW_KIND_ROLE)
        if kind == KIND_GROUP:
            extra = 8 if index.row() > 0 else 2
            return QtCore.QSize(base.width(), max(24, base.height()) + extra)
        return QtCore.QSize(base.width(), max(30, base.height()))

    def _paint_group(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: _ParentIndex,
    ) -> None:
        tokens = theme_manager().tokens()
        view_option = cast(Any, option)
        rect = view_option.rect
        painter.save()
        if index.row() > 0:
            line_y = rect.top() + 4
            painter.setPen(QtGui.QColor(tokens.panel_border))
            painter.drawLine(rect.left() + 8, line_y, rect.right() - 8, line_y)
            rect = rect.adjusted(0, 8, 0, 0)
        font = painter.font()
        font.setBold(True)
        if font.pointSize() > 0:
            font.setPointSize(max(font.pointSize() - 1, 8))
        painter.setFont(font)
        painter.setPen(QtGui.QColor(tokens.text_muted))
        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")
        painter.drawText(
            rect.adjusted(10, 0, -8, 0),
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        painter.restore()


def populate_rank_sidebar_list(rank_list: QtWidgets.QListWidget) -> None:
    rank_list.clear()
    for group_title, spec in iter_rank_sidebar_rows():
        if spec is None:
            header = QtWidgets.QListWidgetItem(group_title)
            header.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            header.setData(RANK_ID_ROLE, "")
            header.setData(RANK_ROW_KIND_ROLE, KIND_GROUP)
            rank_list.addItem(header)
            continue
        item = QtWidgets.QListWidgetItem(spec.title)
        item.setData(RANK_ID_ROLE, spec.id)
        item.setData(RANK_ROW_KIND_ROLE, KIND_RANK)
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
        self.rank_list.setItemDelegate(RankSidebarDelegate(self.rank_list))
        self.rank_list.setSpacing(1)
        self.rank_list.setToolTip("单击切换榜单；再次点击当前榜单可恢复涨幅榜")
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


def _rank_sidebar_target_width(expanded: bool) -> int:
    return RANK_SIDEBAR_EXPANDED_WIDTH if expanded else RANK_SIDEBAR_COLLAPSED_WIDTH


def _rank_splitter_total_width(splitter: QtWidgets.QSplitter) -> int:
    width = splitter.width()
    if width > 0:
        return width
    sizes = splitter.sizes()
    return max(sum(sizes), RANK_SIDEBAR_EXPANDED_WIDTH + 200)


def clamp_rank_splitter_sizes(page: QuotesPage) -> None:
    """侧栏为固定宽度，splitter 左栏须与之一致，避免展开后出现空白条。"""
    sidebar = getattr(page, "rank_sidebar", None)
    splitter = getattr(page, "_rank_splitter", None)
    if sidebar is None or splitter is None or splitter.count() < 2:
        return
    target = _rank_sidebar_target_width(sidebar.is_expanded())
    sizes = splitter.sizes()
    if len(sizes) >= 2 and sizes[0] == target:
        return
    total = _rank_splitter_total_width(splitter)
    splitter.blockSignals(True)
    splitter.setSizes([target, max(total - target, 0)])
    splitter.blockSignals(False)


class MarketRankSplitterResizeFilter(QtCore.QObject):
    """窗口或 splitter 尺寸变化时重新对齐榜单栏宽度。"""

    def __init__(self, page: QuotesPage) -> None:
        super().__init__(page)
        self._page = page

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.Resize:
            clamp_rank_splitter_sizes(self._page)
        return super().eventFilter(watched, event)


def sync_rank_splitter_for_expansion(page: QuotesPage, expanded: bool) -> None:
    """折叠时收窄 splitter 左侧整栏，仅保留折叠钮。"""
    sidebar = getattr(page, "rank_sidebar", None)
    splitter = getattr(page, "_rank_splitter", None)
    if sidebar is None or splitter is None or splitter.count() < 2:
        return

    width = _rank_sidebar_target_width(expanded)
    sidebar.setMinimumWidth(width)
    sidebar.setMaximumWidth(width)
    total = _rank_splitter_total_width(splitter)
    splitter.blockSignals(True)
    splitter.setSizes([width, max(total - width, 0)])
    splitter.blockSignals(False)
