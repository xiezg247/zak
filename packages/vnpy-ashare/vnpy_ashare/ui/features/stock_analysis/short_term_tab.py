"""个股分析：短线（打板 / 龙头）Tab。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.stock.short_term import ShortTermProfile
from vnpy_ashare.quotes.radar.radar_limit_ladder import board_display_text
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import MetricTile, content_card, hint_label, section_title, tab_page
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


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


class ShortTermAnalysisTab(QtWidgets.QWidget):
    peer_activated = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = hint_label("")
        self._summary = hint_label("")
        self._summary.setObjectName("OverviewScreeningBadge")

        self._boards_tile = MetricTile("连板", subtitle="涨停档案")
        self._seal_tile = MetricTile("封单", subtitle="涨停日")
        self._open_tile = MetricTile("开板次数")
        self._first_tile = MetricTile("首封", subtitle="末封见下")
        self._last_tile = MetricTile("末封")

        limit_metrics = QtWidgets.QHBoxLayout()
        limit_metrics.setSpacing(10)
        for tile in (self._boards_tile, self._seal_tile, self._open_tile, self._first_tile, self._last_tile):
            limit_metrics.addWidget(tile, stretch=1)
        limit_wrap = QtWidgets.QWidget()
        limit_wrap.setLayout(limit_metrics)

        self._leader_tile = MetricTile("龙头地位", subtitle="行业内")
        self._sector_tile = MetricTile("所属行业")
        self._emotion_tile = MetricTile("情绪阶段", subtitle="允许模式")
        self._mode_tile = MetricTile("推荐买点")

        leader_metrics = QtWidgets.QHBoxLayout()
        leader_metrics.setSpacing(10)
        for tile in (self._leader_tile, self._sector_tile, self._emotion_tile, self._mode_tile):
            leader_metrics.addWidget(tile, stretch=1)
        leader_wrap = QtWidgets.QWidget()
        leader_wrap.setLayout(leader_metrics)

        self._regulatory_label = hint_label("")
        self._regulatory_label.setObjectName("PageHint")

        self._peer_table = QtWidgets.QTableWidget(0, 5)
        self._peer_table.setHorizontalHeaderLabels(["代码", "名称", "分层", "连板", "涨跌幅"])
        configure_data_table(self._peer_table)
        self._peer_table.cellDoubleClicked.connect(self._on_peer_double_clicked)

        self._mode_table = QtWidgets.QTableWidget(0, 3)
        self._mode_table.setHorizontalHeaderLabels(["模式", "得分", "理由"])
        configure_data_table(self._mode_table)
        self._mode_table.horizontalHeader().setStretchLastSection(True)

        page = tab_page(
            self._status,
            self._summary,
            content_card(limit_wrap, margins=(8, 8, 8, 8)),
            content_card(leader_wrap, margins=(8, 8, 8, 8)),
            self._regulatory_label,
            content_card(section_title("同板块龙头（双击打开）"), self._peer_table),
            content_card(section_title("买点模式"), self._mode_table),
            stretch_index=3,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

    def show_idle(self, message: str = "切换到本 Tab 时加载短线档案") -> None:
        self._status.setText(message)
        self._summary.setText("")
        self._summary.hide()
        self._clear_tiles()
        self._regulatory_label.setText("")
        self._peer_table.setRowCount(0)
        self._mode_table.setRowCount(0)

    def show_loading(self, message: str = "正在加载短线档案…") -> None:
        self._status.setText(message)
        self._summary.setText("")
        self._summary.hide()
        for tile in (
            self._boards_tile,
            self._seal_tile,
            self._open_tile,
            self._first_tile,
            self._last_tile,
            self._leader_tile,
            self._sector_tile,
            self._emotion_tile,
            self._mode_tile,
        ):
            tile.set_value("…")
        self._regulatory_label.setText("")
        self._peer_table.setRowCount(0)
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
            self._open_tile,
            self._first_tile,
            self._last_tile,
            self._leader_tile,
            self._sector_tile,
            self._emotion_tile,
            self._mode_tile,
        ):
            tile.set_value("—")

    def _render_summary(self, profile: ShortTermProfile) -> None:
        entry = profile.entry_mode or {}
        boards = profile.limit_times
        board_text = board_display_text(int(boards)) if boards is not None and boards >= 1 else "非涨停"
        tier = profile.leader_tier_label or "—"
        mode = str(entry.get("recommended_label") or "观望")
        stage = str(entry.get("emotion_stage_label") or "—")
        allow = "可新开" if entry.get("allow_new_positions", True) else "不宜新开"
        self._summary.setText(f"{board_text} · {tier} · 推荐「{mode}」 · 情绪「{stage}」· {allow}")
        self._summary.show()

    def _render_limit(self, profile: ShortTermProfile) -> None:
        limit = profile.limit_today or {}
        boards = profile.limit_times
        if boards is not None and boards >= 1:
            self._boards_tile.set_value(board_display_text(int(boards)))
        else:
            self._boards_tile.set_value("—", subtitle="未涨停")

        self._seal_tile.set_value(_fmt_amount(limit.get("fd_amount")))
        open_times = limit.get("open_times")
        self._open_tile.set_value(str(open_times) if open_times not in (None, "") else "—")
        self._first_tile.set_value(_fmt_time(limit.get("first_time")))
        self._last_tile.set_value(_fmt_time(limit.get("last_time")))

    def _render_leader(self, profile: ShortTermProfile) -> None:
        rank_text = f"#{profile.sector_rank}" if profile.sector_rank > 0 else "—"
        tier = profile.leader_tier_label or "—"
        self._leader_tile.set_value(tier, subtitle=f"行业排名 {rank_text}")
        self._sector_tile.set_value(profile.sector_name or "—")

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
            return
        prefix = "监管异动 · "
        if profile.regulatory_risk_level == "high":
            prefix = "监管高风险 · "
        elif profile.regulatory_risk_level == "watch":
            prefix = "监管关注 · "
        self._regulatory_label.setText(prefix + summary)

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
                    item.setForeground(QtCore.Qt.GlobalColor.white)
                    color = pct_change_color(change, tokens)
                    if color:
                        item.setData(QtCore.Qt.ItemDataRole.ForegroundRole, color)
                elif col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._peer_table.setItem(row_idx, col_idx, item)
        self._peer_table.resizeColumnsToContents()

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

    def _on_peer_double_clicked(self, row: int, _column: int) -> None:
        item = self._peer_table.item(row, 0)
        if item is None:
            return
        vt_symbol = str(item.data(QtCore.Qt.ItemDataRole.UserRole) or item.text()).strip()
        name = str(item.data(QtCore.Qt.ItemDataRole.UserRole + 1) or "")
        if vt_symbol:
            self.peer_activated.emit(vt_symbol, name)
