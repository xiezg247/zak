"""平台相关适配（macOS GUI 进程注册等）。"""

from vnpy_common.platform.macos_gui import (
    configure_macos_before_qt,
    install_macos_gui_log_filter,
    promote_macos_gui_process,
)

__all__ = [
    "configure_macos_before_qt",
    "install_macos_gui_log_filter",
    "promote_macos_gui_process",
]
