"""雷达单卡 chrome：header / body / footer 控件组装。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.quotes.radar.radar_catalog import (
    RadarCardSpec,
    default_refresh_ms_for_card,
    default_variant_for_card,
    full_refresh_options_for_card,
    refresh_options_for_card,
    variants_for_card,
)
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import load_radar_full_refresh_every
from vnpy_ashare.ui.quotes.page.config import load_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.card_layout import (
    BODY_PAGE_ROWS,
    RADAR_ROW_SPACING,
    card_shows_sector_actions,
    kind_badge_presentation,
)


def _select_combo_data(combo: QtWidgets.QComboBox, value: object) -> bool:
    index = combo.findData(value)
    if index < 0:
        return False
    combo.blockSignals(True)
    combo.setCurrentIndex(index)
    combo.blockSignals(False)
    return True


@dataclass(slots=True)
class CardHeaderChrome:
    title: QtWidgets.QLabel
    kind_badge: QtWidgets.QLabel
    mode_badge: QtWidgets.QLabel
    variant_combo: QtWidgets.QComboBox
    refresh_interval_combo: QtWidgets.QComboBox
    full_refresh_combo: QtWidgets.QComboBox
    refresh_button: QtWidgets.QToolButton
    refresh_menu_button: QtWidgets.QToolButton
    layout: QtWidgets.QHBoxLayout


@dataclass(slots=True)
class CardBodyChrome:
    subtitle: QtWidgets.QLabel
    ai_hint: QtWidgets.QLabel
    rows_host: QtWidgets.QWidget
    rows_layout: QtWidgets.QVBoxLayout
    empty_label: QtWidgets.QLabel
    body_stack: QtWidgets.QStackedWidget


@dataclass(slots=True)
class CardFooterChrome:
    meta_label: QtWidgets.QLabel
    ai_button: QtWidgets.QPushButton
    view_run_button: QtWidgets.QPushButton
    sector_flow_button: QtWidgets.QPushButton | None
    sector_rotation_button: QtWidgets.QPushButton | None
    add_all_button: QtWidgets.QPushButton
    layout: QtWidgets.QHBoxLayout


def build_card_header(spec: RadarCardSpec) -> CardHeaderChrome:
    """标题 + 徽章 + 变体/刷新控件。信号由调用方连接。"""
    header = QtWidgets.QHBoxLayout()
    header.setSpacing(8)
    header.setContentsMargins(0, 0, 0, 0)

    title = QtWidgets.QLabel(spec.title)
    title.setObjectName("RadarCardTitle")
    header.addWidget(
        title,
        stretch=1,
        alignment=QtCore.Qt.AlignmentFlag.AlignVCenter,
    )

    actions = QtWidgets.QHBoxLayout()
    actions.setSpacing(6)
    actions.setContentsMargins(0, 0, 0, 0)

    badge_group = QtWidgets.QWidget()
    badge_group.setObjectName("RadarCardBadgeGroup")
    badge_layout = QtWidgets.QHBoxLayout(badge_group)
    badge_layout.setContentsMargins(0, 0, 0, 0)
    badge_layout.setSpacing(4)

    kind_text, kind_object = kind_badge_presentation(spec.mode)
    kind_badge = QtWidgets.QLabel(kind_text)
    kind_badge.setObjectName(kind_object)
    badge_layout.addWidget(kind_badge)

    mode_badge = QtWidgets.QLabel("")
    mode_badge.setObjectName("RadarCardModeBadge")
    badge_layout.addWidget(mode_badge)
    actions.addWidget(badge_group)

    variant_combo = QtWidgets.QComboBox()
    variant_combo.setObjectName("RadarCardVariant")
    if spec.has_task_variants:
        for variant in variants_for_card(spec.id):
            variant_combo.addItem(variant.label, variant.key)
        default_key = default_variant_for_card(spec.id)
        if default_key:
            _select_combo_data(variant_combo, default_key)
        variant_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        variant_combo.setMinimumContentsLength(5)
        variant_combo.setMaximumWidth(108)
        actions.addWidget(variant_combo)
    else:
        variant_combo.hide()

    refresh_interval_combo = QtWidgets.QComboBox()
    refresh_interval_combo.setObjectName("RadarCardRefreshInterval")
    refresh_interval_combo.setToolTip("自动刷新周期")
    refresh_options = refresh_options_for_card(spec.id)
    if refresh_options:
        for option in refresh_options:
            refresh_interval_combo.addItem(option.label, option.ms)
        default_ms = load_radar_card_refresh_ms(spec.id, default_refresh_ms_for_card(spec.id))
        if not _select_combo_data(refresh_interval_combo, int(default_ms)):
            _select_combo_data(refresh_interval_combo, default_refresh_ms_for_card(spec.id))
        actions.addWidget(refresh_interval_combo)
    else:
        refresh_interval_combo.hide()

    full_refresh_combo = QtWidgets.QComboBox()
    full_refresh_combo.setObjectName("RadarCardFullRefreshInterval")
    full_refresh_combo.setToolTip("自动刷新时，每隔多少次全量重算指标（其余仅更新现价 / 涨幅）")
    full_refresh_options = full_refresh_options_for_card(spec.id)
    if full_refresh_options:
        for option in full_refresh_options:
            full_refresh_combo.addItem(option.label, option.ms)
        default_every = load_radar_full_refresh_every(spec.id)
        if not _select_combo_data(full_refresh_combo, int(default_every)):
            _select_combo_data(full_refresh_combo, load_radar_full_refresh_every(spec.id))
        actions.addWidget(full_refresh_combo)
    else:
        full_refresh_combo.hide()

    refresh_button = QtWidgets.QToolButton()
    refresh_button.setObjectName("RadarCardRefresh")
    refresh_button.setText("↻")
    refresh_button.setToolTip("全量刷新")

    refresh_menu_button = QtWidgets.QToolButton()
    refresh_menu_button.setObjectName("RadarCardRefreshMenu")
    refresh_menu_button.setText("▾")
    refresh_menu_button.setToolTip("更多刷新选项")
    refresh_menu_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
    refresh_menu = QtWidgets.QMenu(refresh_menu_button)
    refresh_menu_button.setMenu(refresh_menu)

    refresh_group = QtWidgets.QWidget()
    refresh_group.setObjectName("RadarCardRefreshGroup")
    refresh_layout = QtWidgets.QHBoxLayout(refresh_group)
    refresh_layout.setContentsMargins(0, 0, 0, 0)
    refresh_layout.setSpacing(4)
    refresh_layout.addWidget(refresh_button)
    refresh_layout.addWidget(refresh_menu_button)

    header_divider = QtWidgets.QWidget()
    header_divider.setObjectName("RadarCardHeaderDivider")
    header_divider.setFixedSize(1, 14)
    actions.addWidget(header_divider)
    actions.addWidget(refresh_group)

    actions_host = QtWidgets.QWidget()
    actions_host.setObjectName("RadarCardHeaderActions")
    actions_host.setLayout(actions)
    header.addWidget(
        actions_host,
        alignment=QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight,
    )

    return CardHeaderChrome(
        title=title,
        kind_badge=kind_badge,
        mode_badge=mode_badge,
        variant_combo=variant_combo,
        refresh_interval_combo=refresh_interval_combo,
        full_refresh_combo=full_refresh_combo,
        refresh_button=refresh_button,
        refresh_menu_button=refresh_menu_button,
        layout=header,
    )


def build_card_body() -> CardBodyChrome:
    """副标题 / AI 提示 / 行列表与空态。"""
    subtitle = QtWidgets.QLabel("")
    subtitle.setObjectName("RadarCardSubtitle")
    subtitle.setWordWrap(True)
    subtitle.setMaximumHeight(30)
    subtitle.setMinimumHeight(0)

    ai_hint = QtWidgets.QLabel("")
    ai_hint.setObjectName("RadarCardAiHint")
    ai_hint.setWordWrap(True)
    ai_hint.hide()

    rows_host = QtWidgets.QWidget()
    rows_host.setObjectName("RadarCardRowsHost")
    rows_layout = QtWidgets.QVBoxLayout(rows_host)
    rows_layout.setContentsMargins(0, 0, 0, 0)
    rows_layout.setSpacing(RADAR_ROW_SPACING)

    rows_page = QtWidgets.QWidget()
    rows_page.setObjectName("RadarCardRowsPage")
    rows_page_layout = QtWidgets.QVBoxLayout(rows_page)
    rows_page_layout.setContentsMargins(0, 0, 0, 0)
    rows_page_layout.setSpacing(0)
    rows_page_layout.addWidget(rows_host)

    empty_label = QtWidgets.QLabel("")
    empty_label.setObjectName("RadarCardEmpty")
    empty_label.setWordWrap(True)
    empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    empty_page = QtWidgets.QWidget()
    empty_page.setObjectName("RadarCardEmptyPage")
    empty_page_layout = QtWidgets.QVBoxLayout(empty_page)
    empty_page_layout.setContentsMargins(0, 0, 0, 0)
    empty_page_layout.addStretch(1)
    empty_page_layout.addWidget(empty_label)
    empty_page_layout.addStretch(1)

    body_stack = QtWidgets.QStackedWidget()
    body_stack.setObjectName("RadarCardBodyStack")
    body_stack.addWidget(rows_page)
    body_stack.addWidget(empty_page)
    body_stack.setCurrentIndex(BODY_PAGE_ROWS)
    body_stack.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Minimum,
    )

    return CardBodyChrome(
        subtitle=subtitle,
        ai_hint=ai_hint,
        rows_host=rows_host,
        rows_layout=rows_layout,
        empty_label=empty_label,
        body_stack=body_stack,
    )


def build_card_footer(spec: RadarCardSpec) -> CardFooterChrome:
    """meta + AI / 查看完整 / 板块 / 全部加自选。信号由调用方连接。"""
    footer = QtWidgets.QHBoxLayout()
    footer.setSpacing(8)

    meta_label = QtWidgets.QLabel("")
    meta_label.setObjectName("RadarCardMeta")
    footer.addWidget(meta_label, stretch=1)

    ai_button = QtWidgets.QPushButton("AI")
    ai_button.setObjectName("RadarCardAi")
    ai_button.setFlat(True)
    ai_button.setToolTip("解读本卡片")
    footer.addWidget(ai_button)

    view_run_button = QtWidgets.QPushButton("查看完整")
    view_run_button.setObjectName("RadarCardViewRun")
    view_run_button.setFlat(True)
    view_run_button.hide()
    footer.addWidget(view_run_button)

    sector_flow_button: QtWidgets.QPushButton | None = None
    sector_rotation_button: QtWidgets.QPushButton | None = None
    if card_shows_sector_actions(spec.id):
        sector_flow_button = QtWidgets.QPushButton("板块资金")
        sector_flow_button.setObjectName("RadarCardSectorFlow")
        sector_flow_button.setFlat(True)
        sector_flow_button.setToolTip("打开板块资金监控页并预选主线行业")
        footer.addWidget(sector_flow_button)

        sector_rotation_button = QtWidgets.QPushButton("近15日轮动")
        sector_rotation_button.setObjectName("RadarCardSectorRotation")
        sector_rotation_button.setFlat(True)
        sector_rotation_button.setToolTip("打开板块资金页近15日轮动矩阵并预选主线行业")
        footer.addWidget(sector_rotation_button)

    add_all_button = QtWidgets.QPushButton("全部加自选")
    add_all_button.setObjectName("RadarCardAddAll")
    add_all_button.setFlat(True)
    add_all_button.hide()
    footer.addWidget(add_all_button)

    return CardFooterChrome(
        meta_label=meta_label,
        ai_button=ai_button,
        view_run_button=view_run_button,
        sector_flow_button=sector_flow_button,
        sector_rotation_button=sector_rotation_button,
        add_all_button=add_all_button,
        layout=footer,
    )
