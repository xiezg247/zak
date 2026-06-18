"""AI 工具能力 UI（状态条 + 详情对话框）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.theme.manager import theme_manager
from vnpy_llm.app.engine import LlmEngine
from vnpy_llm.tools.status import ToolProviderState, ToolProviderStatus, ToolsStatusSnapshot
from vnpy_llm.ui.dialogs.tool_audit import show_ai_tool_audit_dialog
from vnpy_llm.ui.themed_styles import bind_ai_tools_bar_style, bind_ai_tools_dialog_style

_STATE_LABELS: dict[ToolProviderState, str] = {
    "ready": "已就绪",
    "missing_env": "缺配置",
    "connect_failed": "连接失败",
    "disabled": "未启用",
    "idle": "待连接",
}


class AiToolsStatusBar(QtWidgets.QWidget):
    """AI 面板工具能力摘要条。"""

    open_details_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiToolsStatusBar")
        bind_ai_tools_bar_style(self)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._summary = QtWidgets.QLabel("加载工具能力…")
        self._summary.setObjectName("AiToolsSummary")
        self._summary.setWordWrap(True)
        self._layout.addWidget(self._summary, stretch=1)
        detail_btn = QtWidgets.QPushButton("详情")
        detail_btn.setObjectName("AiToolBtn")
        detail_btn.setFixedWidth(44)
        detail_btn.clicked.connect(self.open_details_requested.emit)
        self._layout.addWidget(detail_btn)

    def apply_snapshot(self, snapshot: ToolsStatusSnapshot) -> None:
        self._summary.setText(snapshot.compact_summary())

    def show_progress(self, text: str) -> None:
        self._summary.setText(f"⏳ {text}")
        self._summary.setStyleSheet(f"color: {theme_manager().tokens().accent};")

    def hide_progress(self) -> None:
        self._summary.setStyleSheet("")


class AiToolsDialog(QtWidgets.QDialog):
    """AI 工具能力详情。"""

    reload_requested = QtCore.Signal()

    def __init__(
        self,
        engine: LlmEngine,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("AI 工具能力")
        self.setMinimumSize(520, 420)
        bind_ai_tools_dialog_style(self)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self._meta_label = QtWidgets.QLabel()
        self._meta_label.setObjectName("AiToolsMeta")
        root.addWidget(self._meta_label)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("AiToolsScroll")
        container = QtWidgets.QWidget()
        self._list_layout = QtWidgets.QVBoxLayout(container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        audit_btn = QtWidgets.QPushButton("工具审计")
        audit_btn.setObjectName("AiToolBtn")
        audit_btn.clicked.connect(self._open_audit)
        buttons.addWidget(audit_btn)
        reload_btn = QtWidgets.QPushButton("重新加载")
        reload_btn.setObjectName("AiToolBtn")
        reload_btn.clicked.connect(self._on_reload)
        buttons.addWidget(reload_btn)
        close_btn = QtWidgets.QPushButton("关闭")
        close_btn.setObjectName("AiToolBtn")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        root.addLayout(buttons)

    def refresh(self) -> None:
        snapshot = self.engine.get_tools_status()
        self._meta_label.setText(f"共 {snapshot.total_tools} 个 OpenAI 工具 · Skills {snapshot.ready_skill_count} · MCP {snapshot.ready_mcp_count}")
        while self._list_layout.count():
            layout_item = self._list_layout.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.deleteLater()
        self._list_layout.addWidget(self._section_title("Skills"))
        if snapshot.skills:
            for provider in snapshot.skills:
                self._list_layout.addWidget(self._make_card(provider))
        else:
            self._list_layout.addWidget(self._empty_label("暂无 Skill"))
        self._list_layout.addWidget(self._section_title("MCP"))
        if snapshot.mcps:
            for provider in snapshot.mcps:
                self._list_layout.addWidget(self._make_card(provider))
        else:
            self._list_layout.addWidget(self._empty_label("暂无 MCP Provider"))
        self._list_layout.addStretch()

    def _section_title(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("AiToolsSection")
        return label

    def _empty_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("AiToolsEmpty")
        return label

    def _make_card(self, item: ToolProviderStatus) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName(f"AiToolsCard_{item.state}")
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(item.title)
        title.setObjectName("AiToolsCardTitle")
        header.addWidget(title)
        header.addStretch()
        badge = QtWidgets.QLabel(_STATE_LABELS[item.state])
        badge.setObjectName(f"AiToolsBadge_{item.state}")
        header.addWidget(badge)
        layout.addLayout(header)

        detail_parts = [item.summary]
        if item.tool_count:
            detail_parts.append(f"工具数：{item.tool_count}")
        if item.missing_env:
            detail_parts.append(f"缺少配置：{', '.join(item.missing_env)}")
        if item.error:
            detail_parts.append(f"错误：{item.error[:200]}")
        detail = QtWidgets.QLabel("\n".join(part for part in detail_parts if part))
        detail.setObjectName("AiToolsCardDetail")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        return frame

    def _on_reload(self) -> None:
        self.engine.reload_tools()
        self.refresh()
        self.reload_requested.emit()

    def _open_audit(self) -> None:
        show_ai_tool_audit_dialog(self.engine, self)


def show_ai_tools_dialog(
    engine: LlmEngine,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    dialog = AiToolsDialog(engine, parent)
    dialog.exec()
