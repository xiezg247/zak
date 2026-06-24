"""在 import Qt 之前执行 macOS GUI 进程适配（由 launcher 首行加载）。"""

from vnpy_common.platform.macos_gui import bootstrap_macos_gui_runtime

bootstrap_macos_gui_runtime(before_qt=True)
