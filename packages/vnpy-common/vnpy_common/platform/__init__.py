"""平台相关适配（macOS GUI 进程注册等）。"""

from vnpy_common.platform.macos_gui import (
    bootstrap_macos_gui_runtime,
    configure_macos_before_qt,
    install_macos_gui_log_filter,
    is_benign_macos_gui_log,
    promote_macos_gui_process,
)

__all__ = [
    "bootstrap_macos_gui_runtime",
    "configure_macos_before_qt",
    "install_macos_gui_log_filter",
    "is_benign_macos_gui_log",
    "promote_macos_gui_process",
]
