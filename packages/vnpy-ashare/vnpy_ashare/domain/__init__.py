"""领域模型与 A 股通用规则。

子包::

    core/      数值解析、环境变量
    time/      东八区时间、交易日历、交易时段、行情时间
    symbols/   标的代码互转（TickFlow / Tushare / vt_symbol）
    market/    指数、板块、资金流、广度、情绪、概览
    screener/  选股结果、配方、维度命中、行情快照
    trading/   记账、计划、持仓、策略信号、风控
    radar/     雷达卡片与龙头评分
    data/      K 线元数据与健康检查
    models/    笔记等领域实体
    jobs/      后台任务结果
    notifications/ 通知投递模型
    tech/      技术指标纯函数
    ai/        AI 触发的 UI 写操作
"""
