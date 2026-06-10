"""AI 工具调用审计日志查看。"""

from __future__ import annotations

import json
from typing import Any

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.tools.audit import list_recent_tool_calls
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.feedback import page_notify
from vnpy_llm.ui.themed_styles import bind_ai_tools_dialog_style

_TOOL_LABELS: dict[str, str] = {
    "get_quote_context": "读取当前上下文",
    "get_watchlist": "查询自选池",
    "get_bars_summary": "查询K线概览",
    "get_bars_data": "加载K线数据",
    "diagnose_stock": "综合诊断",
    "technical_snapshot": "分析技术形态",
    "list_strategy_signals": "查询策略信号",
    "historical_pattern_summary": "统计历史走势",
    "get_screening_context": "读取选股结果",
    "propose_screening": "解析选股条件",
    "list_screeners": "列出选股条件",
    "screen_by_condition": "执行选股筛选",
    "screen_by_pattern": "执行形态选股",
    "list_strategies": "列出可用策略",
    "get_backtest_result": "读取回测结果",
    "list_backtest_history": "查询回测历史",
    "add_to_watchlist": "加入自选",
    "remove_from_watchlist": "移出自选",
}


def _tool_display(name: str) -> str:
    if name in _TOOL_LABELS:
        return _TOOL_LABELS[name]
    if name.startswith("mcp_tdx_"):
        suffix = name.removeprefix("mcp_tdx_")
        return f"通达信 MCP ({suffix})"
    return name


def _args_summary(arguments: dict[str, Any]) -> str:
    if not arguments:
        return "—"
    text = json.dumps(arguments, ensure_ascii=False)
    return text if len(text) <= 80 else text[:77] + "…"


class AiToolAuditDialog(QtWidgets.QDialog):
    """只读展示 llm_tool_calls 表。"""

    def __init__(
        self,
        engine: LlmEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self._rows: list[dict[str, Any]] = []
        self.setWindowTitle("AI 工具审计")
        self.setMinimumSize(760, 520)
        bind_ai_tools_dialog_style(self)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        toolbar = QtWidgets.QHBoxLayout()
        self._session_only = QtWidgets.QCheckBox("仅当前会话")
        self._session_only.setChecked(True)
        self._session_only.stateChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(self._session_only)

        toolbar.addWidget(QtWidgets.QLabel("条数"))
        self._limit_spin = QtWidgets.QSpinBox()
        self._limit_spin.setRange(20, 200)
        self._limit_spin.setValue(80)
        self._limit_spin.valueChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(self._limit_spin)

        toolbar.addStretch()
        refresh_btn = QtWidgets.QPushButton("刷新")
        refresh_btn.setObjectName("AiToolBtn")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        copy_btn = QtWidgets.QPushButton("复制详情")
        copy_btn.setObjectName("AiToolBtn")
        copy_btn.clicked.connect(self._copy_detail)
        toolbar.addWidget(copy_btn)
        root.addLayout(toolbar)

        self._meta_label = QtWidgets.QLabel()
        self._meta_label.setObjectName("AiToolsMeta")
        root.addWidget(self._meta_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["时间", "工具", "状态", "参数", "结果预览"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        self.detail = QtWidgets.QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("选中一行以查看完整参数与返回预览")
        self.detail.setMaximumBlockCount(5000)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setObjectName("AiToolBtn")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def refresh(self) -> None:
        session_id = self.engine.session_id if self._session_only.isChecked() else None
        limit = self._limit_spin.value()
        self._rows = list_recent_tool_calls(session_id=session_id, limit=limit)
        self.table.setRowCount(0)
        for row_data in self._rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            tool_name = str(row_data.get("tool_name", ""))
            success = bool(row_data.get("success", True))
            status_text = "成功" if success else "失败"
            tokens = theme_manager().tokens()
            status_color = tokens.semantic_success if success else tokens.semantic_error

            time_item = QtWidgets.QTableWidgetItem(str(row_data.get("created_at", "")))
            tool_item = QtWidgets.QTableWidgetItem(_tool_display(tool_name))
            tool_item.setToolTip(tool_name)
            status_item = QtWidgets.QTableWidgetItem(status_text)
            status_item.setForeground(QtGui.QColor(status_color))
            args_item = QtWidgets.QTableWidgetItem(_args_summary(dict(row_data.get("arguments") or {})))
            preview_item = QtWidgets.QTableWidgetItem(str(row_data.get("result_preview", "")))

            for item in (time_item, tool_item, status_item, args_item, preview_item):
                item.setData(QtCore.Qt.ItemDataRole.UserRole, row_data)
            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, tool_item)
            self.table.setItem(row, 2, status_item)
            self.table.setItem(row, 3, args_item)
            self.table.setItem(row, 4, preview_item)

        scope = "当前会话" if session_id else "全部会话"
        self._meta_label.setText(f"{scope} · 最近 {len(self._rows)} 条工具调用")
        if self._rows:
            self.table.selectRow(0)
        else:
            self.detail.clear()

    def _selected_row(self) -> dict[str, Any] | None:
        items = self.table.selectedItems()
        if not items:
            return None
        data = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else None

    def _on_selection_changed(self) -> None:
        row_data = self._selected_row()
        if row_data is None:
            self.detail.clear()
            return
        payload = {
            "id": row_data.get("id"),
            "session_id": row_data.get("session_id"),
            "created_at": row_data.get("created_at"),
            "tool_name": row_data.get("tool_name"),
            "success": row_data.get("success"),
            "arguments": row_data.get("arguments"),
            "result_preview": row_data.get("result_preview"),
        }
        self.detail.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

    def _copy_detail(self) -> None:
        text = self.detail.toPlainText().strip()
        if not text:
            page_notify(self, "请先选中一条审计记录")
            return
        QtWidgets.QApplication.clipboard().setText(text)


def show_ai_tool_audit_dialog(
    engine: LlmEngine,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    dialog = AiToolAuditDialog(engine, parent)
    dialog.exec()
