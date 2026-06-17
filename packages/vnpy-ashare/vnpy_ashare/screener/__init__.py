"""选股（P0 行情 + P1 Tushare 基本面）。

目录约定：
- ``run/``：执行、run_store、导出
- ``recipe/``：多维度配方
- ``preset/``：内置方案与规则
- ``pattern/``：形态选股
- ``data/``：选股数据源编排（Redis + Tushare 合并）
- ``dimensions/``：配方维度实现
- ``batch/``：批量回测 / 下载
- ``draft/``：AI 草稿与 NL
- ``auto/``、``reference/``、``sector/``、``sentiment/``
"""
