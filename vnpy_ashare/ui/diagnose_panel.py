"""诊断结果卡片（与 AnalysisService.diagnose JSON 对齐）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.styles import FALL_COLOR, FLAT_COLOR, RISE_COLOR


def _pct_color(value: float | None) -> str:
    if value is None:
        return FLAT_COLOR
    if value > 0:
        return RISE_COLOR
    if value < 0:
        return FALL_COLOR
    return FLAT_COLOR


def format_diagnose_html(payload: dict[str, Any]) -> str:
    """将 diagnose JSON 渲染为 RichText HTML。"""
    if payload.get("error"):
        return f'<p style="color:#ff5c5c;">{payload["error"]}</p>'

    lines: list[str] = []
    symbol = payload.get("symbol", "")
    name = payload.get("name", "")
    title = f"{name} ({symbol})" if name else symbol
    lines.append(f'<p style="margin:0 0 8px 0;"><b>{title}</b></p>')

    technical = payload.get("technical") or {}
    if technical:
        ma = technical.get("ma") or {}
        ret = (technical.get("period_return") or {}).get("return_pct")
        ret_color = _pct_color(ret if isinstance(ret, (int, float)) else None)
        ret_text = f"{ret:+.2f}%" if isinstance(ret, (int, float)) else "-"
        lines.append(
            '<p style="margin:0 0 4px 0;color:#4a9eff;">技术面</p>'
            f'<ul style="margin:0 0 8px 16px;padding:0;color:#c8c8c8;">'
            f'<li>收盘：{technical.get("last_close", "-")} · 截至 {technical.get("as_of", "-")}</li>'
            f'<li>均线：MA5 {ma.get("ma5", "-")} / MA20 {ma.get("ma20", "-")}</li>'
            f'<li>{technical.get("ma_alignment", "")}</li>'
            f'<li>区间涨跌：<span style="color:{ret_color};">{ret_text}</span></li>'
            f'</ul>'
        )

    reports = payload.get("reports") or []
    if reports:
        lines.append('<p style="margin:0 0 4px 0;color:#4a9eff;">研报摘要</p>')
        lines.append('<ul style="margin:0 0 8px 16px;padding:0;color:#c8c8c8;">')
        for row in reports[:3]:
            broker = row.get("broker") or row.get("org") or ""
            date = row.get("date") or ""
            rating = row.get("rating") or ""
            title_text = row.get("title") or "研报"
            meta = " · ".join(part for part in (broker, date, rating) if part)
            summary = (row.get("summary") or "")[:120]
            lines.append(
                f"<li><b>{title_text}</b>"
                f'{f"（{meta}）" if meta else ""}'
                f"{f'<br/>{summary}…' if summary else ''}</li>"
            )
        if len(reports) > 3:
            lines.append(f"<li>… 另有 {len(reports) - 3} 条</li>")
        lines.append("</ul>")

    warnings = payload.get("warnings") or []
    if warnings:
        lines.append('<p style="margin:0 0 4px 0;color:#f0b429;">提示</p>')
        lines.append('<ul style="margin:0 0 8px 16px;padding:0;color:#f0b429;">')
        for warning in warnings[:4]:
            lines.append(f"<li>{warning}</li>")
        lines.append("</ul>")

    disclaimer = payload.get("disclaimer") or ""
    if disclaimer:
        lines.append(
            f'<p style="margin:8px 0 0 0;color:#6a6a6a;font-size:11px;">{disclaimer}</p>'
        )
    return "".join(lines)


class DiagnosePanel(QtWidgets.QWidget):
    """看盘页右侧诊断卡片。"""

    refresh_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DiagnosePanel")
        self._payload: dict[str, Any] | None = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("快速诊断")
        title.setObjectName("SectionLabel")
        header.addWidget(title)
        header.addStretch()
        self.refresh_btn = QtWidgets.QPushButton("刷新")
        self.refresh_btn.setObjectName("SecondaryButton")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        self.body = QtWidgets.QLabel("选中标的后点击「诊断」或此处刷新")
        self.body.setWordWrap(True)
        self.body.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.body.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft
        )
        self.body.setStyleSheet("color: #8a8a8a; font-size: 12px;")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(220)
        scroll.setWidget(self.body)
        layout.addWidget(scroll)

    def payload(self) -> dict[str, Any] | None:
        return self._payload

    def show_loading(self, symbol: str = "") -> None:
        hint = f"正在诊断 {symbol}…" if symbol else "正在诊断…"
        self.body.setText(f'<p style="color:#8a8a8a;">{hint}</p>')

    def show_result(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.body.setText(format_diagnose_html(payload))

    def clear(self) -> None:
        self._payload = None
        self.body.setText("选中标的后点击「诊断」或此处刷新")
