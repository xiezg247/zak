"""看盘页 UI 子包（Controller / Worker / page_shell）。"""

# 不在包初始化时 eager import 子模块，避免 chart_panel ↔ quotes 循环依赖。

__all__: list[str] = []
