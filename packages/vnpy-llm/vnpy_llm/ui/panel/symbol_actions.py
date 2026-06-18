"""AI 助手消息内标的链接的跳转与右键菜单。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_common.ai.protocol import SymbolRef
from vnpy_common.ai.symbol_navigation import get_symbol_navigation
from vnpy_common.ui.feedback import page_notify
from vnpy_llm.ui.panel.symbol_links import normalize_vt_symbol, parse_symbol_href

if TYPE_CHECKING:
    from vnpy_llm.ui.panel.chat import AiChatPanel


class AssistantSymbolActions:
    """解析 zak://symbol/ 链接并执行看盘/分析/回测等动作。"""

    def __init__(self, panel: AiChatPanel) -> None:
        self._panel = panel

    @property
    def _engine(self):
        return self._panel.engine

    def handle_link_click(self, url: QtCore.QUrl | str) -> bool:
        text = url.toString() if isinstance(url, QtCore.QUrl) else str(url)
        if text.startswith("zak://team-report/"):
            return self._open_team_report_link(text)
        vt_symbol = parse_symbol_href(text)
        if vt_symbol is None:
            return False
        QtCore.QTimer.singleShot(0, lambda vt=vt_symbol: self.open_analysis(vt))
        return True

    def _open_team_report_link(self, href: str) -> bool:
        try:
            from urllib.parse import parse_qs, unquote, urlparse

            parsed = urlparse(href)
            report_id = int(parsed.path.strip("/").split("/", 1)[-1])
            query = parse_qs(parsed.query)
            vt_symbol = unquote((query.get("symbol") or [""])[0])
        except (ValueError, IndexError):
            return False
        if not vt_symbol:
            return False
        nav = self._navigation("笔记中心")
        if nav is None:
            return False
        nav.open_team_report(
            report_id=report_id,
            vt_symbol=vt_symbol,
            main_engine=self._engine.main_engine,
            event_engine=self._engine.event_engine,
            parent=self._panel.window(),
        )
        page_notify(self._panel, f"已在笔记中心打开 {vt_symbol} 分析报告（#{report_id}）", level="success")
        return True

    def symbol_at(self, browser: QtWidgets.QTextBrowser, pos: QtCore.QPoint) -> str | None:
        anchor = browser.anchorAt(pos)
        if not anchor:
            return None
        return parse_symbol_href(anchor)

    def show_menu(
        self,
        parent: QtWidgets.QWidget,
        pos: QtCore.QPoint,
        vt_symbol: str,
        *,
        body: str = "",
    ) -> None:
        item = self._parse_ref(vt_symbol)
        if item is None:
            page_notify(parent, f"无法解析标的：{vt_symbol}", level="warning")
            return
        menu = self._build_menu(item, body=body)
        menu.exec(parent.mapToGlobal(pos))

    def open_analysis(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_ref(vt_symbol, name=name)
        if item is None:
            page_notify(self._panel, f"无法解析标的：{vt_symbol}", level="warning")
            return
        nav = self._navigation("个股分析")
        if nav is None:
            return
        nav.open_analysis(
            item,
            main_engine=self._engine.main_engine,
            event_engine=self._engine.event_engine,
            parent=self._panel.window(),
        )
        QtCore.QTimer.singleShot(0, self._panel._sync_all_bubble_widths)

    def focus_watchlist(self, vt_symbol: str) -> None:
        item = self._parse_ref(vt_symbol)
        if item is None:
            return
        nav = self._navigation("自选")
        if nav is None:
            return
        if nav.focus_watchlist(item, host=self._panel.window()):
            return
        page_notify(self._panel, "无法跳转到自选页", level="warning")

    def open_backtest(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_ref(vt_symbol, name=name)
        if item is None:
            return
        nav = self._navigation("回测")
        if nav is None:
            return
        nav.open_backtest(item, event_engine=self._engine.event_engine)

    def toggle_watchlist(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_ref(vt_symbol, name=name)
        if item is None:
            return
        nav = self._navigation("自选")
        if nav is None:
            return
        self._notify_result(nav.toggle_watchlist(item, main_engine=self._engine.main_engine))

    def open_reference_peer(self, vt_symbol: str, *, name: str = "") -> None:
        item = self._parse_ref(vt_symbol, name=name)
        if item is None:
            return
        nav = self._navigation("找同类")
        if nav is None:
            return
        nav.open_reference_peer(
            item,
            main_engine=self._engine.main_engine,
            parent=self._panel.window(),
        )

    def copy_vt_symbol(self, vt_symbol: str) -> None:
        vt = normalize_vt_symbol(vt_symbol) or vt_symbol
        QtGui.QGuiApplication.clipboard().setText(vt)
        page_notify(self._panel, f"已复制 {vt}", level="success")

    def fill_ai_prompt(self, prompt: str) -> None:
        self._panel.set_input_text(prompt)

    def _navigation(self, feature: str):
        nav = get_symbol_navigation()
        if nav is None:
            page_notify(self._panel, f"{feature}需要 vnpy-ashare 插件", level="warning")
        return nav

    def _parse_ref(self, vt_symbol: str, *, name: str = "") -> SymbolRef | None:
        nav = get_symbol_navigation()
        if nav is None:
            return None
        return nav.parse(vt_symbol, name=name)

    def _notify_result(self, result: str) -> None:
        if ":" not in result:
            page_notify(self._panel, result, level="warning")
            return
        level, message = result.split(":", 1)
        page_notify(self._panel, message, level=level)

    def _build_menu(self, item: SymbolRef, *, body: str = "") -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self._panel)
        vt = item.vt_symbol
        title = item.name or vt
        nav = get_symbol_navigation()

        analyze = menu.addAction("个股分析")
        analyze.triggered.connect(lambda: self.open_analysis(vt, name=item.name))

        focus = menu.addAction("在自选定位")
        focus.triggered.connect(lambda: self.focus_watchlist(vt))

        menu.addSeparator()

        if nav is not None and nav.watchlist_contains(item):
            watchlist_action = menu.addAction("移出自选")
        else:
            watchlist_action = menu.addAction("加入自选")
        watchlist_action.triggered.connect(lambda: self.toggle_watchlist(vt, name=item.name))

        backtest = menu.addAction("策略回测")
        backtest.triggered.connect(lambda: self.open_backtest(vt, name=item.name))

        peer = menu.addAction("找同类…")
        peer.triggered.connect(lambda: self.open_reference_peer(vt, name=item.name))

        menu.addSeparator()

        ai_menu = menu.addMenu("继续问 AI")
        self._populate_ai_submenu(ai_menu, item)

        menu.addSeparator()

        report = menu.addAction(f"存为分析报告（{title}）…")
        report.triggered.connect(lambda _checked=False, b=body: self._save_report(vt, item.name, body=b))

        journal = menu.addAction(f"追加到流水（{title}）")
        journal.triggered.connect(lambda _checked=False, b=body: self._save_journal(vt, item.name, body=b))

        copy_action = menu.addAction("复制 vt_symbol")
        copy_action.triggered.connect(lambda: self.copy_vt_symbol(vt))

        return menu

    def _populate_ai_submenu(self, menu: QtWidgets.QMenu, item: SymbolRef) -> None:
        nav = get_symbol_navigation()
        if nav is None:
            disabled = menu.addAction("需要 vnpy-ashare 插件")
            disabled.setEnabled(False)
            return
        entries = nav.build_completion_items(item)
        if not entries:
            disabled = menu.addAction("无法解析标的")
            disabled.setEnabled(False)
            return
        for entry in entries:
            action = menu.addAction(entry.label)
            action.triggered.connect(lambda _checked=False, prompt=entry.prompt: self.fill_ai_prompt(prompt))

    def _save_report(self, vt_symbol: str, name: str, *, body: str) -> None:
        item = self._parse_ref(vt_symbol, name=name)
        if item is None:
            page_notify(self._panel, "无法解析标的", level="warning")
            return
        text = body.strip()
        if not text:
            page_notify(self._panel, "消息内容为空", level="info")
            return
        nav = self._navigation("笔记")
        if nav is None:
            return
        if nav.save_report(
            main_engine=self._engine.main_engine,
            text=text,
            item=item,
            parent=self._panel,
        ):
            page_notify(self._panel, f"已保存分析报告（{item.vt_symbol}）", level="success")

    def _save_journal(self, vt_symbol: str, name: str, *, body: str) -> None:
        item = self._parse_ref(vt_symbol, name=name)
        if item is None:
            page_notify(self._panel, "无法解析标的", level="warning")
            return
        text = body.strip()
        if not text:
            page_notify(self._panel, "消息内容为空", level="info")
            return
        nav = self._navigation("笔记")
        if nav is None:
            return
        if nav.save_journal(main_engine=self._engine.main_engine, text=text, item=item):
            page_notify(self._panel, f"已追加流水（{item.vt_symbol}）", level="success")
        else:
            page_notify(self._panel, "保存失败或内容被截断为空", level="warning")
