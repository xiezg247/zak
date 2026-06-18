"""出站通知（飞书 Webhook 等）。

子包::

    core/       事件 ID、出站消息模型
    prefs/      QSettings 订阅与卡片开关
    rules/      发送规则（开关、去重、限频）
    content/    正文模板、飞书卡片、出站组装
    pipeline/   异步投递队列
    channels/   Webhook 等渠道实现
    triggers/   业务侧扫描触发（持仓异动等）
"""
