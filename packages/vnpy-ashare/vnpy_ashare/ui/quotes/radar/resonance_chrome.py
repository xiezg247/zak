"""共振侧栏 chrome：handle / header / tabs / toolbar 组装。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.quotes.radar.resonance_layout import (
    COLLAPSE_BUTTON_SIZE,
    RESONANCE_CONTENT_MAX_WIDTH,
    RESONANCE_CONTENT_MIN_WIDTH,
    RESONANCE_FILTER_OPTIONS,
    RESONANCE_HANDLE_WIDTH,
    RESONANCE_TABS,
    RadarResonanceTab,
    resonance_empty_message,
)


@dataclass(slots=True)
class ResonanceHandleChrome:
    handle: QtWidgets.QWidget
    collapse_button: QtWidgets.QToolButton


@dataclass(slots=True)
class ResonanceHeaderChrome:
    count_label: QtWidgets.QLabel
    gate_banner: QtWidgets.QLabel
    risk_banner: QtWidgets.QLabel
    stats_label: QtWidgets.QLabel
    filter_combo: QtWidgets.QComboBox
    layout: QtWidgets.QVBoxLayout


@dataclass(slots=True)
class ResonanceTabsChrome:
    tabs: QtWidgets.QTabWidget
    lists: dict[RadarResonanceTab, QtWidgets.QListWidget]
    stacks: dict[RadarResonanceTab, QtWidgets.QStackedWidget]
    empty_labels: dict[RadarResonanceTab, QtWidgets.QLabel]


@dataclass(slots=True)
class ResonanceToolbarChrome:
    add_all_button: QtWidgets.QPushButton
    dragon_watchlist_button: QtWidgets.QPushButton
    focus_button: QtWidgets.QPushButton
    ai_button: QtWidgets.QPushButton
    screener_button: QtWidgets.QPushButton
    leader_button: QtWidgets.QPushButton
    weights_button: QtWidgets.QPushButton
    plan_button: QtWidgets.QPushButton
    eod_button: QtWidgets.QPushButton
    layout: QtWidgets.QGridLayout


def build_resonance_handle(parent: QtWidgets.QWidget) -> ResonanceHandleChrome:
    handle = QtWidgets.QWidget(parent)
    handle.setObjectName("RadarResonanceHandle")
    handle.setFixedWidth(RESONANCE_HANDLE_WIDTH)
    handle_layout = QtWidgets.QVBoxLayout(handle)
    handle_layout.setContentsMargins(0, 0, 0, 0)
    handle_layout.setSpacing(0)

    collapse_button = QtWidgets.QToolButton(handle)
    collapse_button.setObjectName("RadarResonanceCollapseButton")
    collapse_button.setCheckable(True)
    collapse_button.setAutoRaise(True)
    collapse_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
    collapse_button.setFixedSize(COLLAPSE_BUTTON_SIZE, COLLAPSE_BUTTON_SIZE)

    handle_layout.addStretch(1)
    handle_layout.addWidget(
        collapse_button,
        alignment=QtCore.Qt.AlignmentFlag.AlignHCenter,
    )
    handle_layout.addStretch(1)
    return ResonanceHandleChrome(handle=handle, collapse_button=collapse_button)


def build_resonance_header() -> ResonanceHeaderChrome:
    header = QtWidgets.QVBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(2)

    title_row = QtWidgets.QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title = QtWidgets.QLabel("共振列表")
    title.setObjectName("RadarResonanceTitle")
    title_row.addWidget(title, stretch=1)
    count_label = QtWidgets.QLabel("0")
    count_label.setObjectName("RadarResonanceCount")
    title_row.addWidget(count_label)
    header.addLayout(title_row)

    hint = QtWidgets.QLabel("多卡同时出现的标的汇总")
    hint.setObjectName("RadarResonanceHint")
    header.addWidget(hint)

    gate_banner = QtWidgets.QLabel("")
    gate_banner.setObjectName("RadarResonanceGateBanner")
    gate_banner.setWordWrap(True)
    gate_banner.hide()
    header.addWidget(gate_banner)

    risk_banner = QtWidgets.QLabel("")
    risk_banner.setObjectName("RadarResonanceRiskBanner")
    risk_banner.setWordWrap(True)
    risk_banner.hide()
    header.addWidget(risk_banner)

    stats_label = QtWidgets.QLabel("")
    stats_label.setObjectName("RadarResonanceStats")
    header.addWidget(stats_label)

    filter_row = QtWidgets.QHBoxLayout()
    filter_row.setContentsMargins(0, 0, 0, 0)
    filter_row.addWidget(QtWidgets.QLabel("过滤"))
    filter_combo = QtWidgets.QComboBox()
    filter_combo.setObjectName("RadarResonanceFilter")
    for mode, label in RESONANCE_FILTER_OPTIONS:
        filter_combo.addItem(label, mode)
    filter_row.addWidget(filter_combo, stretch=1)
    header.addLayout(filter_row)

    return ResonanceHeaderChrome(
        count_label=count_label,
        gate_banner=gate_banner,
        risk_banner=risk_banner,
        stats_label=stats_label,
        filter_combo=filter_combo,
        layout=header,
    )


def build_resonance_tabs() -> ResonanceTabsChrome:
    tabs = QtWidgets.QTabWidget()
    tabs.setObjectName("RadarResonanceTabs")
    lists: dict[RadarResonanceTab, QtWidgets.QListWidget] = {}
    stacks: dict[RadarResonanceTab, QtWidgets.QStackedWidget] = {}
    empty_labels: dict[RadarResonanceTab, QtWidgets.QLabel] = {}

    for tab_key, tab_label in RESONANCE_TABS:
        page = QtWidgets.QWidget()
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(0, 4, 0, 0)
        page_layout.setSpacing(0)

        stack = QtWidgets.QStackedWidget()
        list_widget = QtWidgets.QListWidget()
        list_widget.setObjectName("RadarResonanceList")
        list_widget.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        list_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        list_widget.setSpacing(4)
        list_widget.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        list_widget.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        empty_page = QtWidgets.QWidget()
        empty_layout = QtWidgets.QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(12, 24, 12, 24)
        empty_label = QtWidgets.QLabel(resonance_empty_message(tab_key))
        empty_label.setObjectName("RadarResonanceEmpty")
        empty_label.setWordWrap(True)
        empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()
        empty_layout.addWidget(empty_label)
        empty_layout.addStretch()

        stack.addWidget(list_widget)
        stack.addWidget(empty_page)
        page_layout.addWidget(stack, stretch=1)

        lists[tab_key] = list_widget
        stacks[tab_key] = stack
        empty_labels[tab_key] = empty_label
        tabs.addTab(page, tab_label)

    return ResonanceTabsChrome(
        tabs=tabs,
        lists=lists,
        stacks=stacks,
        empty_labels=empty_labels,
    )


def build_resonance_toolbar() -> ResonanceToolbarChrome:
    toolbar = QtWidgets.QGridLayout()
    toolbar.setContentsMargins(0, 0, 0, 0)
    toolbar.setHorizontalSpacing(6)
    toolbar.setVerticalSpacing(6)

    add_all_button = QtWidgets.QPushButton("全部加自选")
    add_all_button.setObjectName("RadarResonanceAddAll")

    dragon_watchlist_button = QtWidgets.QPushButton("龙一入自选")
    dragon_watchlist_button.setObjectName("RadarResonanceDragonWatchlist")
    dragon_watchlist_button.setToolTip("将 leader_pick 龙一加入自选池")

    focus_button = QtWidgets.QPushButton("写入短线关注")
    focus_button.setObjectName("RadarResonanceShortTermFocus")
    focus_button.setToolTip("写入自选池并加入「短线关注」分组")

    ai_button = QtWidgets.QPushButton("AI 解读")
    ai_button.setObjectName("RadarResonanceAi")

    screener_button = QtWidgets.QPushButton("条件选股")
    screener_button.setObjectName("RadarResonanceScreener")

    leader_button = QtWidgets.QPushButton("龙头选股")
    leader_button.setObjectName("RadarResonanceLeader")
    leader_button.setToolTip("按 leader_score 执行龙头选股并打开 Hub")

    weights_button = QtWidgets.QPushButton("权重")
    weights_button.setObjectName("RadarResonanceWeights")
    weights_button.setToolTip("配置各卡片共振加权分")

    plan_button = QtWidgets.QPushButton("生成次日计划")
    plan_button.setObjectName("RadarResonancePlan")
    plan_button.setToolTip("基于情绪周期与共振标的生成次日计划草案")

    eod_button = QtWidgets.QPushButton("盘后解读")
    eod_button.setObjectName("RadarResonanceEod")
    eod_button.setToolTip("今日龙头结构 + 明日观察（AI 预填）")

    toolbar.addWidget(add_all_button, 0, 0)
    toolbar.addWidget(dragon_watchlist_button, 0, 1)
    toolbar.addWidget(focus_button, 1, 0, 1, 2)
    toolbar.addWidget(ai_button, 2, 0)
    toolbar.addWidget(screener_button, 2, 1)
    toolbar.addWidget(leader_button, 3, 0)
    toolbar.addWidget(weights_button, 3, 1)
    toolbar.addWidget(plan_button, 4, 0)
    toolbar.addWidget(eod_button, 4, 1)

    return ResonanceToolbarChrome(
        add_all_button=add_all_button,
        dragon_watchlist_button=dragon_watchlist_button,
        focus_button=focus_button,
        ai_button=ai_button,
        screener_button=screener_button,
        leader_button=leader_button,
        weights_button=weights_button,
        plan_button=plan_button,
        eod_button=eod_button,
        layout=toolbar,
    )


def build_resonance_body() -> QtWidgets.QFrame:
    body = QtWidgets.QFrame()
    body.setObjectName("RadarResonancePanel")
    body.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
    body.setMinimumWidth(RESONANCE_CONTENT_MIN_WIDTH)
    body.setMaximumWidth(RESONANCE_CONTENT_MAX_WIDTH)
    return body
