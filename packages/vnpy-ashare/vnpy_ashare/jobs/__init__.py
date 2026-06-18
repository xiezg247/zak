"""可复用的后台任务（CLI / 定时调度共用）。

子包::

    core/      执行结果、进度日志
    sync/      标的列表、行业、交易日历、停牌
    bars/      日 K 下载与本地补全
    prefetch/  收盘后 Tushare 预拉、板块资金
    financial/ 自选池财报与披露计划
    quotes/    行情采集
    market/    市场摘要预热
    screen/    自动选股、雷达展望扫描
"""
