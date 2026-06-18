"""NL 选股工具执行前 Qt 确认（主线程弹窗）。"""

from __future__ import annotations

import json
from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_llm.config.nl_screening_prefs import load_nl_screening_confirm_enabled

NL_SCREENING_CONFIRM_TOOLS = frozenset({"propose_screening", "propose_recipe"})

_bridge: NlScreeningConfirmBridge | None = None


class NlScreeningConfirmBridge(QtCore.QObject):
    @QtCore.Slot(str, str, result=bool)
    def ask(self, tool_name: str, summary: str) -> bool:
        parent = QtWidgets.QApplication.activeWindow()
        title = "确认执行选股" if tool_name == "propose_screening" else "确认执行多因子选股"
        box = QtWidgets.QMessageBox(parent)
        box.setIcon(QtWidgets.QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(summary)
        box.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
        return box.exec() == QtWidgets.QMessageBox.StandardButton.Yes


def ensure_confirm_bridge() -> NlScreeningConfirmBridge:
    global _bridge
    if _bridge is None:
        _bridge = NlScreeningConfirmBridge()
    return _bridge


def build_nl_screening_confirm_summary(tool_name: str, arguments: dict[str, Any]) -> str:
    if tool_name == "propose_recipe":
        intent = str(arguments.get("intent") or arguments.get("query") or "").strip()
        recipe_id = str(arguments.get("recipe_id") or "").strip()
        top_n = arguments.get("top_n")
        parts = ["AI 将解析并执行多因子选股。"]
        if intent:
            parts.append(f"意图：{intent}")
        if recipe_id:
            parts.append(f"配方：{recipe_id}")
        if top_n is not None:
            parts.append(f"返回数量：{top_n}")
        return "\n".join(parts)

    intent = str(arguments.get("intent") or "").strip()
    scheme = str(arguments.get("scheme_name") or "").strip()
    preset = str(arguments.get("preset") or "").strip()
    top_n = arguments.get("top_n")
    parts = ["AI 将解析并执行条件选股。"]
    if scheme:
        parts.append(f"方案：{scheme}")
    elif preset:
        parts.append(f"Preset：{preset}")
    if intent:
        parts.append(f"意图：{intent}")
    if top_n is not None:
        parts.append(f"返回数量：{top_n}")
    return "\n".join(parts)


def _ask_on_main_thread(tool_name: str, summary: str) -> bool:
    bridge = ensure_confirm_bridge()
    app = QtWidgets.QApplication.instance()
    if app is None:
        return True

    if QtCore.QThread.currentThread() is app.thread():
        return bridge.ask(tool_name, summary)

    result: list[bool] = []
    loop = QtCore.QEventLoop()

    def _show() -> None:
        result.append(bridge.ask(tool_name, summary))
        loop.quit()

    QtCore.QTimer.singleShot(0, _show)
    loop.exec()
    return result[0] if result else False


def confirm_nl_screening_tool(tool_name: str, arguments: dict[str, Any]) -> bool:
    if tool_name not in NL_SCREENING_CONFIRM_TOOLS:
        return True
    if not load_nl_screening_confirm_enabled():
        return True
    summary = build_nl_screening_confirm_summary(tool_name, arguments)
    return _ask_on_main_thread(tool_name, summary)


def cancelled_nl_screening_result(tool_name: str) -> str:
    return json.dumps(
        {"status": "cancelled", "tool": tool_name, "message": "用户取消了选股执行"},
        ensure_ascii=False,
    )
