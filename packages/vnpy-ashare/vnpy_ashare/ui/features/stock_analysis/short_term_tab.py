"""个股分析：短线（打板 / 龙头）Tab。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.stock.short_term import ShortTermProfile
from vnpy_ashare.quotes.radar.radar_limit_ladder import board_display_text
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import (
    MetricTile,
    configure_document_tab_widget,
    content_card,
    frameless_scroll,
    hint_label,
    section_title,
    tab_page,
    tile_grid,
)
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_TABLE_HEADER_HEIGHT = 28
_TABLE_ROW_HEIGHT = 30


def _fmt_amount(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1e8:
        return f"{number / 1e8:.2f}亿"
    if abs(number) >= 1e4:
        return f"{number / 1e4:.1f}万"
    return f"{number:,.0f}"


def _fmt_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    if len(text) == 6 and text.isdigit():
        return f"{text[:2]}:{text[2:4]}:{text[4:6]}"
    if len(text) == 4 and text.isdigit():
        return f"{text[:2]}:{text[2:4]}"
    return text


def _fit_table_height(
    table: QtWidgets.QTableWidget,
    *,
    min_rows: int = 2,
    max_rows: int = 8,
) -> None:
    """按行数收紧表格高度，超出 max_rows 时保留内部滚动。"""
    row_count = table.rowCount()
    visible = min(max(row_count, min_rows), max_rows)
    height = _TABLE_HEADER_HEIGHT + visible * _TABLE_ROW_HEIGHT + 4
    table.setMinimumHeight(height)
    table.setMaximumHeight(height)


class ShortTermAnalysisTab(QtWidgets.QWidget):
    peer_activated = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        self._status = hint_label("")
        self._summary = hint_label("")
        self._summary.setObjectName("OverviewScreeningBadge")

        self._boards_tile = MetricTile("连板", subtitle="涨停档案")
        self._seal_tile = MetricTile("封单", subtitle="涨停日")
        self._strength_tile = MetricTile("封板强度")
        self._open_tile = MetricTile("开板次数")
        self._first_tile = MetricTile("首封")
        self._last_tile = MetricTile("末封")

        self._limit_idle_hint = hint_label("")
        self._seal_state_label = hint_label("")
        self._limit_card = content_card(
            section_title("今日涨停档案"),
            tile_grid(
                [
                    self._boards_tile,
                    self._seal_tile,
                    self._strength_tile,
                    self._open_tile,
                    self._first_tile,
                    self._last_tile,
                ],
                columns=3,
                min_tile_width=96,
            ),
            self._seal_state_label,
            margins=(8, 8, 8, 8),
            spacing=8,
        )

        self._leader_tile = MetricTile("龙头地位", subtitle="行业内")
        self._sector_tile = MetricTile("所属行业")
        self._emotion_tile = MetricTile("情绪阶段", subtitle="允许模式")
        self._mode_tile = MetricTile("推荐买点")
        self._stats_tile = MetricTile("近20日涨停", subtitle="开板 / 未开")

        leader_card = content_card(
            tile_grid(
                [
                    self._leader_tile,
                    self._sector_tile,
                    self._stats_tile,
                    self._emotion_tile,
                    self._mode_tile,
                ],
                columns=5,
                min_tile_width=100,
            ),
            margins=(8, 8, 8, 8),
        )

        self._regulatory_label = hint_label("")
        self._regulatory_label.setObjectName("PageHint")

        self._peer_table = QtWidgets.QTableWidget(0, 5)
        self._peer_table.setHorizontalHeaderLabels(["代码", "名称", "分层", "连板", "涨跌幅"])
        configure_data_table(self._peer_table)
        self._peer_table.cellDoubleClicked.connect(self._on_peer_double_clicked)

        self._history_table = QtWidgets.QTableWidget(0, 6)
        self._history_table.setHorizontalHeaderLabels(["日期", "连板", "首封", "末封", "封单", "开板"])
        configure_data_table(self._history_table)

        self._top_list_table = QtWidgets.QTableWidget(0, 5)
        self._top_list_table.setHorizontalHeaderLabels(["日期", "涨跌幅", "换手", "净买额", "上榜理由"])
        configure_data_table(self._top_list_table)
        self._top_list_table.horizontalHeader().setStretchLastSection(True)

        self._inst_buy_table = QtWidgets.QTableWidget(0, 3)
        self._inst_buy_table.setHorizontalHeaderLabels(["买入前五", "买入额", "净买额"])
        configure_data_table(self._inst_buy_table)
        self._inst_buy_table.horizontalHeader().setStretchLastSection(True)

        self._inst_sell_table = QtWidgets.QTableWidget(0, 3)
        self._inst_sell_table.setHorizontalHeaderLabels(["卖出前五", "卖出额", "净买额"])
        configure_data_table(self._inst_sell_table)
        self._inst_sell_table.horizontalHeader().setStretchLastSection(True)

        self._top_inst_hint = hint_label("")

        inst_row = QtWidgets.QHBoxLayout()
        inst_row.setSpacing(8)
        inst_row.addWidget(self._inst_buy_table, stretch=1)
        inst_row.addWidget(self._inst_sell_table, stretch=1)
        inst_wrap = QtWidgets.QWidget()
        inst_wrap.setLayout(inst_row)

        top_list_page = tab_page(self._top_list_table, self._top_inst_hint, inst_wrap, stretch_index=0)
        detail_tabs = configure_document_tab_widget(QtWidgets.QTabWidget())
        detail_tabs.setMinimumHeight(220)
        detail_tabs.addTab(self._history_table, "近20日涨停")
        detail_tabs.addTab(top_list_page, "龙虎榜")

        self._mode_table = QtWidgets.QTableWidget(0, 3)
        self._mode_table.setHorizontalHeaderLabels(["模式", "得分", "理由"])
        configure_data_table(self._mode_table)
        self._mode_table.horizontalHeader().setStretchLastSection(True)

        scroll_body = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(4, 0, 4, 8)
        scroll_layout.setSpacing(10)
        scroll_layout.addWidget(self._limit_idle_hint)
        scroll_layout.addWidget(self._limit_card)
        scroll_layout.addWidget(leader_card)
        scroll_layout.addWidget(self._regulatory_label)
        scroll_layout.addWidget(
            content_card(section_title("同板块龙头（双击打开）"), self._peer_table),
        )
        scroll_layout.addWidget(content_card(detail_tabs, margins=(4, 4, 4, 4)))
        scroll_layout.addWidget(content_card(section_title("买点模式"), self._mode_table))

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(4, 8, 4, 4)
        root.setSpacing(8)
        root.addWidget(self._status)
        root.addWidget(self._summary)
        root.addWidget(frameless_scroll(scroll_body), stretch=1)

        self._limit_card.hide()
        self._limit_idle_hint.hide()

    def show_idle(self, message: str = "切换到本 Tab 时加载短线档案") -> None:
        self._status.setText(message)
        self._summary.setText("")
        self._summary.hide()
        self._clear_tiles()
        self._limit_card.hide()
        self._limit_idle_hint.hide()
        self._regulatory_label.setText("")
        self._seal_state_label.setText("")
        self._top_inst_hint.setText("")
        self._peer_table.setRowCount(0)
        self._history_table.setRowCount(0)
        self._top_list_table.setRowCount(0)
        self._inst_buy_table.setRowCount(0)
        self._inst_sell_table.setRowCount(0)
        self._mode_table.setRowCount(0)
        _fit_table_height(self._peer_table, min_rows=2, max_rows=3)
        _fit_table_height(self._history_table, min_rows=2, max_rows=4)
        _fit_table_height(self._top_list_table, min_rows=2, max_rows=4)
        _fit_table_height(self._mode_table, min_rows=2, max_rows=3)

    def show_loading(self, message: str = "正在加载短线档案…") -> None:
        self._status.setText(message)
        self._summary.setText("")
        self._summary.hide()
        self._limit_card.show()
        self._limit_idle_hint.hide()
        for tile in (
            self._boards_tile,
            self._seal_tile,
            self._strength_tile,
            self._open_tile,
            self._first_tile,
            self._last_tile,
            self._leader_tile,
            self._sector_tile,
            self._stats_tile,
            self._emotion_tile,
            self._mode_tile,
        ):
            tile.set_value("…")
        self._regulatory_label.setText("")
        self._seal_state_label.setText("")
        self._top_inst_hint.setText("")
        self._peer_table.setRowCount(0)
        self._history_table.setRowCount(0)
        self._top_list_table.setRowCount(0)
        self._inst_buy_table.setRowCount(0)
        self._inst_sell_table.setRowCount(0)
        self._mode_table.setRowCount(0)

    def show_profile(self, profile: ShortTermProfile | None) -> None:
        if profile is None:
            self.show_idle("暂无短线数据")
            return

        self._render_summary(profile)
        self._render_limit(profile)
        self._render_leader(profile)
        self._render_regulatory(profile)
        self._render_peers(profile)
        self._render_history(profile)
        self._render_top_list(profile)
        self._render_modes(profile)

        parts = []
        if profile.trade_date:
            parts.append(f"涨停列表 {profile.trade_date}")
        if profile.message:
            parts.append(profile.message)
        self._status.setText(" · ".join(parts) if parts else "短线档案已加载")

    def _clear_tiles(self) -> None:
        for tile in (
            self._boards_tile,
            self._seal_tile,
            self._strength_tile,
            self._open_tile,
            self._first_tile,
            self._last_tile,
            self._leader_tile,
            self._sector_tile,
            self._stats_tile,
            self._emotion_tile,
            self._mode_tile,
        ):
            tile.set_value("—")

    def _is_limit_up_today(self, profile: ShortTermProfile) -> bool:
        boards = profile.limit_times
        return boards is not None and boards >= 1

    def _render_summary(self, profile: ShortTermProfile) -> None:
        entry = profile.entry_mode or {}
        boards = profile.limit_times
        board_text = board_display_text(int(boards)) if boards is not None and boards >= 1 else "非涨停"
        tier = profile.leader_tier_label or "—"
        mode = str(entry.get("recommended_label") or "观望")
        stage = str(entry.get("emotion_stage_label") or "—")
        allow = "可新开" if entry.get("allow_new_positions", True) else "不宜新开"
        stats = profile.limit_stats
        stats_text = ""
        if stats is not None and stats.limit_up_days > 0:
            stats_text = f" · 近{stats.lookback_days}日涨停 {stats.limit_up_days} 次"
        self._summary.setText(f"{board_text} · {tier} · 推荐「{mode}」 · 情绪「{stage}」· {allow}{stats_text}")
        self._summary.show()

    def _render_limit(self, profile: ShortTermProfile) -> None:
        if self._is_limit_up_today(profile) or profile.limit_today:
            self._limit_card.show()
            self._limit_idle_hint.hide()
        else:
            self._limit_card.hide()
            hint = profile.message.strip() or "今日未在涨停列表，可参考买点模式、历史涨停与龙虎榜"
            self._limit_idle_hint.setText(hint)
            self._limit_idle_hint.show()
            self._seal_state_label.setText("")
            return

        limit = profile.limit_today or {}
        boards = profile.limit_times
        if boards is not None and boards >= 1:
            self._boards_tile.set_value(board_display_text(int(boards)))
        else:
            self._boards_tile.set_value("—", subtitle="未涨停")

        self._seal_tile.set_value(_fmt_amount(limit.get("fd_amount")))
        strength = profile.seal_strength
        strength_label = profile.seal_strength_label or "—"
        if strength is not None:
            self._strength_tile.set_value(
                strength_label,
                subtitle=f"{strength * 100:.0f} 分",
            )
        else:
            self._strength_tile.set_value("—")

        open_times = limit.get("open_times")
        self._open_tile.set_value(str(open_times) if open_times not in (None, "") else "—")
        self._first_tile.set_value(_fmt_time(limit.get("first_time")))
        self._last_tile.set_value(_fmt_time(limit.get("last_time")))

        reopen = profile.seal_reopen_label.strip()
        self._seal_state_label.setText(f"封板状态：{reopen}" if reopen else "")

    def _render_leader(self, profile: ShortTermProfile) -> None:
        rank_text = f"#{profile.sector_rank}" if profile.sector_rank > 0 else "—"
        tier = profile.leader_tier_label or "—"
        self._leader_tile.set_value(tier, subtitle=f"行业排名 {rank_text}")
        self._sector_tile.set_value(profile.sector_name or "—")

        stats = profile.limit_stats
        if stats is not None:
            self._stats_tile.set_value(
                str(stats.limit_up_days),
                subtitle=f"开板 {stats.open_board_days} · 未开 {stats.solid_seal_days}",
            )
        else:
            self._stats_tile.set_value("—")

        entry = profile.entry_mode or {}
        stage = str(entry.get("emotion_stage_label") or "—")
        allowed = entry.get("allowed_mode_labels") or []
        allowed_text = " / ".join(allowed) if allowed else "—"
        self._emotion_tile.set_value(stage, subtitle=allowed_text)

        mode = str(entry.get("recommended_label") or "观望")
        scores = entry.get("scores") or []
        top_score = scores[0].get("score") if scores else None
        subtitle = f"最高 {top_score} 分" if isinstance(top_score, (int, float)) else ""
        self._mode_tile.set_value(mode, subtitle=subtitle)

    def _render_regulatory(self, profile: ShortTermProfile) -> None:
        summary = profile.regulatory_summary.strip()
        if not summary or summary == "暂无异动预警":
            self._regulatory_label.setText("")
            self._regulatory_label.hide()
            return
        prefix = "监管异动 · "
        if profile.regulatory_risk_level == "high":
            prefix = "监管高风险 · "
        elif profile.regulatory_risk_level == "watch":
            prefix = "监管关注 · "
        self._regulatory_label.setText(prefix + summary)
        self._regulatory_label.show()

    def _render_peers(self, profile: ShortTermProfile) -> None:
        peers = profile.sector_peers
        self._peer_table.setRowCount(len(peers))
        tokens = theme_manager().tokens()
        for row_idx, peer in enumerate(peers):
            change = peer.change_pct
            change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "—"
            boards = int(peer.limit_times) if peer.limit_times >= 1 else 0
            values = [
                peer.vt_symbol.split(".")[0],
                peer.name,
                peer.leader_tier_label or "—",
                board_display_text(boards) if boards >= 1 else "—",
                change_text,
            ]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_idx == 0:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, peer.vt_symbol)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, peer.name)
                if col_idx == 4 and isinstance(change, (int, float)):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    color = pct_change_color(change, tokens)
                    if color:
                        item.setData(QtCore.Qt.ItemDataRole.ForegroundRole, color)
                elif col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._peer_table.setItem(row_idx, col_idx, item)
        self._peer_table.resizeColumnsToContents()
        _fit_table_height(self._peer_table, min_rows=3, max_rows=min(len(peers), 8) or 3)

    def _render_history(self, profile: ShortTermProfile) -> None:
        rows = profile.limit_history
        self._history_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            boards = row.limit_times
            board_text = board_display_text(int(boards)) if isinstance(boards, (int, float)) and boards >= 1 else "—"
            values = [
                row.trade_date,
                board_text,
                _fmt_time(row.first_time),
                _fmt_time(row.last_time),
                _fmt_amount(row.fd_amount),
                str(row.open_times) if row.open_times is not None else "—",
            ]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._history_table.setItem(row_idx, col_idx, item)
        self._history_table.resizeColumnsToContents()
        _fit_table_height(self._history_table, min_rows=3, max_rows=6)

    def _render_top_list(self, profile: ShortTermProfile) -> None:
        rows = profile.top_list
        self._top_list_table.setRowCount(len(rows))
        tokens = theme_manager().tokens()
        for row_idx, row in enumerate(rows):
            pct = row.pct_change
            pct_text = f"{pct:+.2f}%" if isinstance(pct, (int, float)) else "—"
            turnover = row.turnover_rate
            turnover_text = f"{turnover:.2f}%" if isinstance(turnover, (int, float)) else "—"
            values = [row.trade_date, pct_text, turnover_text, _fmt_amount(row.net_amount), row.reason or "—"]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_idx == 1 and isinstance(pct, (int, float)):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    color = pct_change_color(pct, tokens)
                    if color:
                        item.setData(QtCore.Qt.ItemDataRole.ForegroundRole, color)
                elif col_idx in {0, 2, 3}:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._top_list_table.setItem(row_idx, col_idx, item)
        self._top_list_table.resizeColumnsToContents()
        _fit_table_height(self._top_list_table, min_rows=2, max_rows=5)

        if profile.top_inst_date and (profile.top_inst_buy or profile.top_inst_sell):
            self._top_inst_hint.setText(f"机构席位（{profile.top_inst_date}）")
        elif rows:
            self._top_inst_hint.setText("暂无机构席位明细（需 5000 积分 top_inst）")
        else:
            self._top_inst_hint.setText("近 60 交易日未上龙虎榜")

        self._fill_inst_table(self._inst_buy_table, profile.top_inst_buy, side="buy")
        self._fill_inst_table(self._inst_sell_table, profile.top_inst_sell, side="sell")
        _fit_table_height(self._inst_buy_table, min_rows=2, max_rows=5)
        _fit_table_height(self._inst_sell_table, min_rows=2, max_rows=5)

    def _fill_inst_table(self, table: QtWidgets.QTableWidget, rows: list[Any], *, side: str) -> None:
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            amount = row.buy if side == "buy" else row.sell
            values = [row.exalter or "—", _fmt_amount(amount), _fmt_amount(row.net_buy)]
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_idx, col_idx, item)
        table.resizeColumnsToContents()

    def _render_modes(self, profile: ShortTermProfile) -> None:
        entry = profile.entry_mode or {}
        scores = entry.get("scores") or []
        warnings = entry.get("warnings") or []
        self._mode_table.setRowCount(len(scores))
        for row_idx, item in enumerate(scores):
            reasons = item.get("reasons") or []
            reason_text = "；".join(str(part) for part in reasons[:3]) if reasons else "—"
            if warnings and row_idx == 0:
                reason_text = f"{reason_text}；{'；'.join(warnings[:2])}" if reason_text != "—" else "；".join(warnings[:2])
            values = [
                str(item.get("label") or "—"),
                f"{item.get('score', '—')}",
                reason_text,
            ]
            for col_idx, text in enumerate(values):
                cell = QtWidgets.QTableWidgetItem(text)
                if col_idx == 1:
                    cell.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._mode_table.setItem(row_idx, col_idx, cell)
        self._mode_table.resizeColumnsToContents()
        _fit_table_height(self._mode_table, min_rows=2, max_rows=max(len(scores), 2))

    def _on_peer_double_clicked(self, row: int, _column: int) -> None:
        item = self._peer_table.item(row, 0)
        if item is None:
            return
        vt_symbol = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or item.text()).strip()
        name = str(item.data(QtCore.Qt.ItemDataRole.UserRole + 1) or "")
        if vt_symbol:
            self.peer_activated.emit(vt_symbol, name)
