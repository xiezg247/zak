"""按 Strategy Profile 的 Playbook 默认章节。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.strategy_profile import StrategyProfileId
from vnpy_ashare.domain.trading.playbook import PlaybookSection

_COMMON_DISCIPLINE = """\
- 不在交易计划外开新仓
- 退潮期无条件空仓，不「手痒」试错
- 11:30 前评估上午必卖；下午弱势不扛单
- 单笔止损与隔日铁则优先于「再等等」
- 复盘后再改规则，盘中不临时改口径
"""

_COMMON_RISK = """\
- 靠盈亏比取胜，靠风控存活
- 单笔风险占账户比例可控；止损纪律优先
- 日亏触及警戒减仓，触及熔断停止新开
- 总回撤与单周回撤超限 → 强制休息
"""

_COMMON_EXECUTION = """\
**隔日卖点铁则**

| 类型 | 条件 | 动作 |
|------|------|------|
| 止盈 | 开盘冲高 3–5% 且量能不足 | 分批止盈 |
| 止盈 | 主板涨停 | 持有；炸板回封无力 → 卖 |
| 止损 | 该高开却低开，30 分钟不翻红 | 无条件止损 |
| 止损 | 日内浮亏 ≤ −5% | 立即止损 |
| 止损 | 跌破开盘价 / 昨收且反弹无力 | 卖 |
"""

_ULTRA_SHORT_TIMING = """\
- **退潮**：龙头跌停、连板批量断板 → **无条件空仓**
- **分歧**：龙头炸板、跟风掉队 → 总仓 ≤ 3 成，仅核心低吸
- **发酵/高潮**：梯队完整 → 龙头/前排，总仓 6–8 成
- **启动**：出现 3 板以上龙头 → 试错首板/二板，3–5 成
- **冰点**：连板高度 ≤ 2、跌停偏多 → 0–1 成或空仓
- 两市成交额 **< 1 万亿** → 降低仓位系数
"""

_ULTRA_SHORT_UNIVERSE = """\
- 只做有辨识度的人气股；拒绝杂毛跟风
- 极致短线主池：涨停 + 连板 + 板块强度 + 换手
- 硬过滤：排除 ST / 停牌；成交额与市值带按 Profile 镜像区为准
- 雷达共振 / 选股结果 → 先入自选，再进信号区（上限 10）
"""

_ULTRA_SHORT_EXECUTION = (
    """\
**三类买点**

| 模式 | 环境 | 规则要点 |
|------|------|----------|
| 打板 | 情绪上升 | 涨停触及；非一字缩量；优先 10:30 前 |
| 半路 | 题材发酵 | 涨幅 3–7%；带量突破；9:40–10:30 |
| 低吸 | 核心分歧 | 回调 MA5 或日内 −3%~−5% 承接 |

"""
    + _COMMON_EXECUTION
)

_SHORT_SWING_TIMING = """\
- 情绪退潮 / 冰点 → 减少新开，以观察为主
- 情绪启动 / 发酵 → 可参与短线波段突破
- 大盘 5 日线拐头向下 → 降低频率，硬过滤偏保守
"""

_SHORT_SWING_UNIVERSE = """\
- 短线放量突破为主；关注题材发酵与龙头趋势延续
- 硬过滤默认「均衡」：流动性 + 市值带 + 排除 ST
- 雷达「未来·展望」与信号区配合，不追杂毛
"""

_SHORT_SWING_EXECUTION = """\
- 买点：突破 + 量比确认（默认 ShortBreakout 策略逻辑）
- 卖点：均线破位、放量滞涨、隔日规则 overlay
- 分 K 辅助见自选信号区；回测验证后再加大仓位
"""

_TEMPLATE_BUILDERS: dict[StrategyProfileId, tuple[tuple[str, str, str, bool], ...]] = {
    "ultra_short": (
        ("timing", "§1 择时 — 做不做", _ULTRA_SHORT_TIMING, False),
        ("universe", "§2 选股 — 做什么", _ULTRA_SHORT_UNIVERSE, False),
        ("execution", "§3 买卖 — 怎么做", _ULTRA_SHORT_EXECUTION, True),
        ("risk", "§4 仓位与风控", _COMMON_RISK, True),
        ("discipline", "§5 纪律", _COMMON_DISCIPLINE, True),
    ),
    "short_swing": (
        ("timing", "§1 择时 — 做不做", _SHORT_SWING_TIMING, False),
        ("universe", "§2 选股 — 做什么", _SHORT_SWING_UNIVERSE, False),
        ("execution", "§3 买卖 — 怎么做", _SHORT_SWING_EXECUTION, True),
        ("risk", "§4 仓位与风控", _COMMON_RISK, True),
        ("discipline", "§5 纪律", _COMMON_DISCIPLINE, True),
    ),
    "medium_watch": (
        ("timing", "§1 择时 — 做不做", _SHORT_SWING_TIMING, False),
        ("universe", "§2 选股 — 做什么", "中线观察：趋势 + 基本面共振；低频率换仓。", False),
        ("execution", "§3 买卖 — 怎么做", "双均线 / 趋势策略；卖点以趋势破坏为准。", True),
        ("risk", "§4 仓位与风控", _COMMON_RISK, True),
        ("discipline", "§5 纪律", _COMMON_DISCIPLINE, True),
    ),
    "trend": (
        ("timing", "§1 择时 — 做不做", "趋势中线：大盘与板块趋势一致时才加仓。", False),
        ("universe", "§2 选股 — 做什么", "趋势 MA 策略；拒绝频繁交易。", False),
        ("execution", "§3 买卖 — 怎么做", "回踩均线买入；跌破慢线减仓。", True),
        ("risk", "§4 仓位与风控", _COMMON_RISK, True),
        ("discipline", "§5 纪律", _COMMON_DISCIPLINE, True),
    ),
}


def playbook_template_sections(profile_id: StrategyProfileId) -> tuple[PlaybookSection, ...]:
    rows = _TEMPLATE_BUILDERS.get(profile_id, _TEMPLATE_BUILDERS["short_swing"])
    return tuple(
        PlaybookSection(
            section_id=section_id,
            title=title,
            body_md=body.strip(),
            collapsed=collapsed,
            sort_order=index,
        )
        for index, (section_id, title, body, collapsed) in enumerate(rows)
    )
