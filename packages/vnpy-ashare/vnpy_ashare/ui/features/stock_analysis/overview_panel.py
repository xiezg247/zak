"""个股分析：概览（仪表盘 + 本地技术面）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.stock.overview_dashboard import (
    DataReadinessItem,
    OverviewAlert,
    OverviewDashboard,
    ReadinessStatus,
)
from vnpy_common.ui.panel_widgets import MetricTile, content_card, hint_label, section_title, tile_grid
from vnpy_common.ui.scroll_area import frameless_scroll_area
from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

_STATUS_LABELS: dict[ReadinessStatus, str] = {
    "ready": "就绪",
    "partial": "偏少",
    "missing": "缺失",
    "unconfigured": "未配置",
}


def _fmt(value: float | None, *, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"


class OverviewAnalysisPanel(QtWidgets.QWidget):
    """概览：数据就绪、关键提醒、本地指标与技术面详情。"""

    jump_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._local_tiles = {
            "close": MetricTile("收盘", subtitle="截至日期"),
            "ma": MetricTile("均线排列"),
            "volume": MetricTile("5日量比"),
            "ret20": MetricTile("20日涨跌"),
            "rs": MetricTile("相对沪深300", subtitle="20日超额"),
        }

        self._ai_hint = hint_label("问小达 / 通达信多维诊断请使用底部「问 AI 解读」，在右侧侧栏与 AI 对话。")
        self._screening_label = hint_label("")
        self._screening_label.setObjectName("OverviewScreeningBadge")
        self._screening_label.hide()

        self._readiness_host = QtWidgets.QWidget()
        self._readiness_layout = QtWidgets.QHBoxLayout(self._readiness_host)
        self._readiness_layout.setContentsMargins(0, 0, 0, 0)
        self._readiness_layout.setSpacing(6)

        self._alerts_host = QtWidgets.QWidget()
        self._alerts_layout = QtWidgets.QVBoxLayout(self._alerts_host)
        self._alerts_layout.setContentsMargins(0, 0, 0, 0)
        self._alerts_layout.setSpacing(4)
        self._alerts_empty = hint_label("暂无关键提醒")
        self._alerts_layout.addWidget(self._alerts_empty)

        self._dashboard_card = content_card(
            section_title("数据就绪"),
            self._readiness_host,
            section_title("关键提醒"),
            self._alerts_host,
            margins=(8, 8, 8, 8),
            spacing=8,
        )

        self._technical_body = QtWidgets.QLabel("")
        self._technical_body.setWordWrap(True)
        self._technical_body.setObjectName("DiagnoseBody")

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._ai_hint)
        layout.addWidget(self._screening_label)
        layout.addWidget(self._dashboard_card)
        layout.addWidget(
            content_card(
                section_title("本地指标"),
                tile_grid(self._local_tiles, columns=3),
                margins=(8, 8, 8, 8),
            )
        )
        layout.addWidget(
            content_card(
                section_title("技术面详情"),
                frameless_scroll_area(self._technical_body),
            ),
            stretch=1,
        )

    def show_loading(self) -> None:
        for tile in self._local_tiles.values():
            tile.set_value("…")
        self._screening_label.hide()
        self._clear_readiness()
        loading = hint_label("正在检查数据就绪与关键提醒…")
        self._readiness_layout.addWidget(loading)
        self._clear_alerts()
        self._alerts_empty.setText("…")
        self._alerts_empty.show()
        self._technical_body.setText("正在分析本地技术面…")

    def show_payload(
        self,
        *,
        technical: dict[str, Any] | None = None,
        technical_text: str = "",
        relative_returns: dict[str, float | None] | None = None,
        dashboard: OverviewDashboard | None = None,
    ) -> None:
        technical = technical or {}
        relative_returns = relative_returns or {}
        tokens = theme_manager().tokens()

        self._render_dashboard(dashboard)

        if technical.get("error"):
            for tile in self._local_tiles.values():
                tile.set_value("—")
        elif technical.get("warnings") and technical.get("last_close") is None:
            for tile in self._local_tiles.values():
                tile.set_value("—")
        else:
            as_of = str(technical.get("as_of") or "—")
            last_close = technical.get("last_close")
            self._local_tiles["close"].set_value(
                _fmt(last_close if isinstance(last_close, (int, float)) else None),
                subtitle=as_of,
            )
            self._local_tiles["ma"].set_value(str(technical.get("ma_alignment") or "—"))
            vol = technical.get("volume_ratio_5d")
            self._local_tiles["volume"].set_value(_fmt(vol if isinstance(vol, (int, float)) else None))
            ret_20 = relative_returns.get("ret_20d")
            if ret_20 is None:
                period = technical.get("period_return") or {}
                ret_20 = period.get("return_pct")
            ret_color = pct_change_color(ret_20 if isinstance(ret_20, (int, float)) else 0, tokens)
            self._local_tiles["ret20"].set_value(
                f"{ret_20:+.2f}%" if isinstance(ret_20, (int, float)) else "—",
                color=ret_color if isinstance(ret_20, (int, float)) else "",
            )
            rs = relative_returns.get("rs_20d")
            rs_color = pct_change_color(rs if isinstance(rs, (int, float)) else 0, tokens)
            self._local_tiles["rs"].set_value(
                f"{rs:+.2f}%" if isinstance(rs, (int, float)) else "—",
                color=rs_color if isinstance(rs, (int, float)) else "",
            )

        self._technical_body.setText(technical_text or "暂无本地技术面")

    def _render_dashboard(self, dashboard: OverviewDashboard | None) -> None:
        if dashboard is None:
            self._screening_label.hide()
            self._clear_readiness()
            self._clear_alerts()
            self._alerts_empty.setText("暂无仪表盘数据")
            self._alerts_empty.show()
            return

        hit = dashboard.screening
        if hit is not None:
            updated = f" · {hit.updated_at}" if hit.updated_at else ""
            self._screening_label.setText(f"选股命中：{hit.condition}（第 {hit.rank}/{hit.total} 名{updated}）")
            self._screening_label.show()
        else:
            self._screening_label.hide()

        self._clear_readiness()
        for item in dashboard.readiness:
            self._readiness_layout.addWidget(self._build_readiness_chip(item))
        self._readiness_layout.addStretch(1)

        self._clear_alerts()
        if dashboard.alerts:
            self._alerts_empty.hide()
            for alert in dashboard.alerts:
                self._alerts_layout.addWidget(self._build_alert_link(alert))
        else:
            self._alerts_empty.setText("暂无关键提醒")
            self._alerts_empty.show()

    def _clear_readiness(self) -> None:
        while self._readiness_layout.count():
            item = self._readiness_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _clear_alerts(self) -> None:
        while self._alerts_layout.count():
            item = self._alerts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._alerts_empty = hint_label("暂无关键提醒")
        self._alerts_layout.addWidget(self._alerts_empty)

    def _build_readiness_chip(self, item: DataReadinessItem) -> QtWidgets.QPushButton:
        status_label = _STATUS_LABELS.get(item.status, item.status)
        button = QtWidgets.QPushButton(f"{item.label} · {status_label}")
        button.setObjectName("OverviewReadinessChip")
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setProperty("readiness_status", item.status)
        button.setToolTip(item.detail or status_label)
        button.style().unpolish(button)
        button.style().polish(button)
        if item.jump_target:
            target = item.jump_target
            button.clicked.connect(lambda _checked=False, t=target: self.jump_requested.emit(t))
        else:
            button.setEnabled(False)
        return button

    def _build_alert_link(self, alert: OverviewAlert) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(alert.text)
        button.setObjectName("OverviewAlertLink")
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setProperty("alert_severity", alert.severity)
        button.style().unpolish(button)
        button.style().polish(button)
        if alert.jump_target:
            target = alert.jump_target
            button.clicked.connect(lambda _checked=False, t=target: self.jump_requested.emit(t))
        else:
            button.setEnabled(False)
        return button
