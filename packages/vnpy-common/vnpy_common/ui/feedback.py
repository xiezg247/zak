"""页面级 Toast 与长任务锁控（TaskGuard）。"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ui.monospace_font import apply_system_monospace_font
from vnpy_common.ui.theme.manager import theme_manager

DEFAULT_TOAST_MS = 4000


class PageToastHost(QtWidgets.QStatusBar):
    """页面底部状态栏：临时提示 + 长任务进度区。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerStatusBar")
        self.setSizeGripEnabled(False)

        self._task_host = QtWidgets.QWidget()
        self._task_host.setObjectName("PageTaskHost")
        task_layout = QtWidgets.QHBoxLayout(self._task_host)
        task_layout.setContentsMargins(0, 0, 8, 0)
        task_layout.setSpacing(8)

        self._task_progress = QtWidgets.QProgressBar()
        self._task_progress.setObjectName("PageTaskProgress")
        self._task_progress.setRange(0, 0)
        self._task_progress.setFixedWidth(120)
        self._task_progress.setFixedHeight(14)
        task_layout.addWidget(self._task_progress)

        self._task_label = QtWidgets.QLabel("")
        self._task_label.setObjectName("PageTaskLabel")
        task_layout.addWidget(self._task_label, stretch=1)

        self._cancel_btn = QtWidgets.QPushButton("取消")
        self._cancel_btn.setObjectName("SecondaryButton")
        self._cancel_btn.setFixedHeight(22)
        self._cancel_btn.hide()
        task_layout.addWidget(self._cancel_btn)

        self._task_host.hide()
        self.addPermanentWidget(self._task_host, stretch=1)

        self._toast_timer = QtCore.QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._clear_transient_message)

        self._cancel_handler: Callable[[], None] | None = None
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)

        theme_manager().bind_stylesheet(self)

    def _on_cancel_clicked(self) -> None:
        if self._cancel_handler is not None:
            self._cancel_handler()

    def show_toast(
        self,
        text: str,
        *,
        level: str = "info",
        timeout_ms: int = DEFAULT_TOAST_MS,
    ) -> None:
        if self._task_host.isVisible():
            return
        self._toast_timer.stop()
        self.showMessage(text)
        color = self._level_color(level)
        if color:
            self.setStyleSheet(f"QStatusBar#ScreenerStatusBar {{ color: {color}; }}")
        if timeout_ms > 0:
            self._toast_timer.start(timeout_ms)

    def info(self, text: str, *, timeout_ms: int = DEFAULT_TOAST_MS) -> None:
        self.show_toast(text, level="info", timeout_ms=timeout_ms)

    def success(self, text: str, *, timeout_ms: int = DEFAULT_TOAST_MS) -> None:
        self.show_toast(text, level="success", timeout_ms=timeout_ms)

    def warning(self, text: str, *, timeout_ms: int = DEFAULT_TOAST_MS) -> None:
        self.show_toast(text, level="warning", timeout_ms=timeout_ms)

    def error(self, text: str, *, timeout_ms: int = DEFAULT_TOAST_MS) -> None:
        self.show_toast(text, level="error", timeout_ms=6000)

    def show_task(self, message: str, *, on_cancel: Callable[[], None] | None = None) -> None:
        self._toast_timer.stop()
        self.clearMessage()
        self.setStyleSheet("")
        self._task_label.setText(message)
        self._cancel_handler = on_cancel
        self._cancel_btn.setVisible(on_cancel is not None)
        self._task_host.show()

    def update_task(self, message: str) -> None:
        self._task_label.setText(message)

    def hide_task(self) -> None:
        self._task_host.hide()
        self._cancel_handler = None
        self._cancel_btn.hide()
        self.clearMessage()
        self.setStyleSheet("")

    def _clear_transient_message(self) -> None:
        if self._task_host.isVisible():
            return
        self.clearMessage()
        self.setStyleSheet("")

    @staticmethod
    def _level_color(level: str) -> str | None:
        tokens = theme_manager().tokens()
        if level == "success":
            return tokens.semantic_success
        if level == "warning":
            return tokens.semantic_warning
        if level == "error":
            return tokens.semantic_error
        return None


class TaskGuard:
    """长任务期间锁控件，主按钮可切换为取消。"""

    def __init__(self, toast: PageToastHost) -> None:
        self._toast = toast
        self._active = False
        self._cancelled = False
        self._saved_states: list[tuple[QtWidgets.QWidget, bool]] = []
        self._primary: QtWidgets.QPushButton | None = None
        self._primary_text = ""
        self._primary_handler: Callable[[], None] | None = None
        self._on_cancel: Callable[[], None] | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def begin(
        self,
        message: str,
        *,
        widgets: Sequence[QtWidgets.QWidget],
        primary: QtWidgets.QPushButton | None = None,
        primary_text: str = "",
        primary_handler: Callable[[], None] | None = None,
        primary_cancel_text: str = "■  取消",
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        if self._active:
            self.end()
        self._active = True
        self._cancelled = False
        self._on_cancel = on_cancel
        self._saved_states = [(widget, widget.isEnabled()) for widget in widgets]
        for widget, _enabled in self._saved_states:
            widget.setEnabled(False)

        if primary is not None and primary_handler is not None:
            self._primary = primary
            self._primary_text = primary_text or primary.text()
            self._primary_handler = primary_handler
            primary.clicked.disconnect()
            primary.setText(primary_cancel_text)
            primary.setEnabled(True)
            primary.clicked.connect(self._trigger_cancel)

        cancel_action = self._trigger_cancel if on_cancel is not None else None
        self._toast.show_task(message, on_cancel=cancel_action)

    def end(self) -> None:
        if not self._active:
            self._toast.hide_task()
            return
        self._active = False
        self._restore_primary()
        for widget, enabled in self._saved_states:
            widget.setEnabled(enabled)
        self._saved_states.clear()
        self._on_cancel = None
        self._toast.hide_task()

    def update_message(self, message: str) -> None:
        if self._active:
            self._toast.update_task(message)

    def _trigger_cancel(self) -> None:
        if not self._active or self._cancelled:
            return
        self._cancelled = True
        self._toast.update_task("正在取消…")
        if self._on_cancel is not None:
            self._on_cancel()

    def _restore_primary(self) -> None:
        primary = self._primary
        if primary is None:
            return
        primary.clicked.disconnect()
        if self._primary_handler is not None:
            primary.clicked.connect(self._primary_handler)
        primary.setText(self._primary_text)
        self._primary = None
        self._primary_text = ""
        self._primary_handler = None


class ConfirmDialog(QtWidgets.QDialog):
    """统一样式的确认对话框（破坏性操作等）。"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        title: str,
        message: str,
        *,
        confirm_text: str = "确定",
        cancel_text: str = "取消",
        destructive: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)

        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)

        buttons = QtWidgets.QDialogButtonBox()
        cancel_btn = buttons.addButton(cancel_text, QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        confirm_btn = buttons.addButton(confirm_text, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        if destructive:
            confirm_btn.setObjectName("DangerButton")
        else:
            confirm_btn.setObjectName("PrimaryRunButton")
        cancel_btn.setObjectName("SecondaryButton")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        theme_manager().bind_stylesheet(self)


def confirm_action(
    parent: QtWidgets.QWidget | None,
    title: str,
    message: str,
    *,
    confirm_text: str = "确定",
    cancel_text: str = "取消",
    destructive: bool = False,
) -> bool:
    dialog = ConfirmDialog(
        parent,
        title,
        message,
        confirm_text=confirm_text,
        cancel_text=cancel_text,
        destructive=destructive,
    )
    return dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted


class InfoDialog(QtWidgets.QDialog):
    """统一样式的只读信息对话框（快捷键帮助等）。"""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        title: str,
        message: str,
        *,
        ok_text: str = "关闭",
        monospace: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)

        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(message)
        label.setWordWrap(not monospace)
        label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        if monospace:
            label.setFont(apply_system_monospace_font(label.font()))
        layout.addWidget(label)

        buttons = QtWidgets.QDialogButtonBox()
        ok_btn = buttons.addButton(ok_text, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        ok_btn.setObjectName("PrimaryRunButton")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        theme_manager().bind_stylesheet(self)


def show_info_dialog(
    parent: QtWidgets.QWidget | None,
    title: str,
    message: str,
    *,
    ok_text: str = "关闭",
    monospace: bool = False,
) -> None:
    InfoDialog(parent, title, message, ok_text=ok_text, monospace=monospace).exec()


def find_page_toast(widget: QtWidgets.QWidget | None) -> PageToastHost | None:
    """沿父链查找页面级 Toast。"""
    current = widget
    while current is not None:
        toast = getattr(current, "_toast", None)
        if isinstance(toast, PageToastHost):
            return toast
        current = current.parentWidget()
    return None


def page_notify(
    widget: QtWidgets.QWidget | None,
    message: str,
    *,
    level: str = "info",
    title: str = "提示",
) -> None:
    """优先 Toast，找不到则回退模态提示。"""
    toast = find_page_toast(widget)
    if toast is not None:
        notifier = getattr(toast, level, toast.info)
        notifier(message)
        return
    if level in ("error", "warning"):
        QtWidgets.QMessageBox.warning(widget, title, message)
    else:
        QtWidgets.QMessageBox.information(widget, title, message)
