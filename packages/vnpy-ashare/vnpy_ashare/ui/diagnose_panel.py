"""诊断结果卡片（与 AnalysisService.diagnose JSON 对齐）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.ui.theme import theme_manager
from vnpy_ashare.ui.theme.html_palette import html_palette
from vnpy_ashare.ui.theme.market_colors import pct_change_color
from vnpy_ashare.ui.theme.tokens import ThemeTokens


def _pct_color(value: float | None, *, tokens: ThemeTokens | None = None) -> str:
    return pct_change_color(value, tokens or theme_manager().tokens())


def format_diagnose_html(payload: dict[str, Any], *, tokens: ThemeTokens | None = None) -> str:
    """将 diagnose JSON 渲染为 RichText HTML。"""
    colors = html_palette(tokens or theme_manager().tokens())
    if payload.get("error"):
        return f'<p style="color:{colors.error};">{payload["error"]}</p>'

    lines: list[str] = []
    symbol = payload.get("symbol", "")
    name = payload.get("name", "")
    title = f"{name} ({symbol})" if name else symbol
    lines.append(f'<p style="margin:0 0 8px 0;"><b>{title}</b></p>')

    quote = payload.get("quote") or {}
    if quote:
        change_pct = quote.get("change_pct")
        ret_color = _pct_color(change_pct if isinstance(change_pct, (int, float)) else None, tokens=tokens)
        ret_text = f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "-"
        industry = quote.get("industry") or ""
        lines.append(
            f'<p style="margin:0 0 4px 0;color:{colors.section};">行情</p>'
            f'<ul style="margin:0 0 8px 16px;padding:0;color:{colors.body};">'
            f"<li>现价：{quote.get('last_price', '-')} · "
            f'涨跌：<span style="color:{ret_color};">{ret_text}</span></li>'
            f"{f'<li>行业：{industry}</li>' if industry else ''}"
            f"</ul>"
        )

    technical = payload.get("technical") or {}
    if technical.get("fields"):
        macd = technical.get("macd")
        dif = technical.get("dif")
        dea = technical.get("dea")
        lines.append(
            f'<p style="margin:0 0 4px 0;color:{colors.section};">技术面</p>'
            f'<ul style="margin:0 0 8px 16px;padding:0;color:{colors.body};">'
            f"<li>MACD {macd if macd is not None else '-'} · "
            f"DIF {dif if dif is not None else '-'} · "
            f"DEA {dea if dea is not None else '-'}</li>"
            f"</ul>"
        )

    fundamental = payload.get("fundamental") or {}
    if fundamental.get("fields"):
        pe = fundamental.get("pe_ttm")
        roe = fundamental.get("roe")
        lines.append(
            f'<p style="margin:0 0 4px 0;color:{colors.section};">基本面</p>'
            f'<ul style="margin:0 0 8px 16px;padding:0;color:{colors.body};">'
            f"<li>PE(TTM) {pe if pe is not None else '-'} · "
            f"ROE {roe if roe is not None else '-'}%</li>"
            f"</ul>"
        )

    capital_flow = payload.get("capital_flow") or {}
    if capital_flow.get("main_net") is not None:
        main_net = capital_flow["main_net"]
        lines.append(
            f'<p style="margin:0 0 4px 0;color:{colors.section};">资金面</p>'
            f'<ul style="margin:0 0 8px 16px;padding:0;color:{colors.body};">'
            f"<li>主力净额：{main_net:,.0f}</li>"
            f"</ul>"
        )

    if not quote and not technical.get("fields"):
        technical = payload.get("technical") or {}
        if technical:
            ma = technical.get("ma") or {}
            ret = (technical.get("period_return") or {}).get("return_pct")
            ret_color = _pct_color(ret if isinstance(ret, (int, float)) else None, tokens=tokens)
            ret_text = f"{ret:+.2f}%" if isinstance(ret, (int, float)) else "-"
            lines.append(
                f'<p style="margin:0 0 4px 0;color:{colors.section};">技术面</p>'
                f'<ul style="margin:0 0 8px 16px;padding:0;color:{colors.body};">'
                f"<li>收盘：{technical.get('last_close', '-')} · 截至 {technical.get('as_of', '-')}</li>"
                f"<li>均线：MA5 {ma.get('ma5', '-')} / MA20 {ma.get('ma20', '-')}</li>"
                f"<li>{technical.get('ma_alignment', '')}</li>"
                f'<li>区间涨跌：<span style="color:{ret_color};">{ret_text}</span></li>'
                f"</ul>"
            )

    reports = payload.get("reports") or []
    if reports:
        lines.append(f'<p style="margin:0 0 4px 0;color:{colors.section};">研报摘要</p>')
        lines.append(f'<ul style="margin:0 0 8px 16px;padding:0;color:{colors.body};">')
        for row in reports[:3]:
            broker = row.get("broker") or row.get("org") or ""
            date = row.get("date") or ""
            rating = row.get("rating") or ""
            title_text = row.get("title") or "研报"
            meta = " · ".join(part for part in (broker, date, rating) if part)
            summary = (row.get("summary") or "")[:120]
            lines.append(f"<li><b>{title_text}</b>{f'（{meta}）' if meta else ''}{f'<br/>{summary}…' if summary else ''}</li>")
        if len(reports) > 3:
            lines.append(f"<li>… 另有 {len(reports) - 3} 条</li>")
        lines.append("</ul>")

    warnings = payload.get("warnings") or []
    if warnings:
        lines.append(f'<p style="margin:0 0 4px 0;color:{colors.warning};">提示</p>')
        lines.append(f'<ul style="margin:0 0 8px 16px;padding:0;color:{colors.warning};">')
        for warning in warnings[:4]:
            lines.append(f"<li>{warning}</li>")
        lines.append("</ul>")

    disclaimer = payload.get("disclaimer") or ""
    if disclaimer:
        lines.append(f'<p style="margin:8px 0 0 0;color:{colors.muted};font-size:11px;">{disclaimer}</p>')
    return "".join(lines)


class DiagnosePanel(QtWidgets.QWidget):
    """看盘页右侧诊断卡片。"""

    refresh_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DiagnosePanel")
        self._payload: dict[str, Any] | None = None
        self._loading_hint: str | None = None

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
        self.body.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.body.setObjectName("DiagnoseBody")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(220)
        scroll.setWidget(self.body)
        layout.addWidget(scroll)
        theme_manager().register_callback(self._on_theme_changed)

    def _on_theme_changed(self, tokens: ThemeTokens) -> None:
        if self._loading_hint is not None:
            colors = html_palette(tokens)
            self.body.setText(f'<p style="color:{colors.label};">{self._loading_hint}</p>')
        elif self._payload is not None:
            self.body.setText(format_diagnose_html(self._payload, tokens=tokens))

    def payload(self) -> dict[str, Any] | None:
        return self._payload

    def show_loading(self, symbol: str = "") -> None:
        self._payload = None
        self._loading_hint = f"正在诊断 {symbol}…" if symbol else "正在诊断…"
        colors = html_palette(theme_manager().tokens())
        self.body.setText(f'<p style="color:{colors.label};">{self._loading_hint}</p>')

    def show_result(self, payload: dict[str, Any]) -> None:
        self._loading_hint = None
        self._payload = payload
        self.body.setText(format_diagnose_html(payload))

    def clear(self) -> None:
        self._payload = None
        self._loading_hint = None
        self.body.setText("选中标的后点击「诊断」或此处刷新")
