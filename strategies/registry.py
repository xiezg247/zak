"""A 股策略元数据：供回测页说明区、文档与 AI 工具共用。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyMeta:
    class_name: str
    title: str
    summary: str
    tags: tuple[str, ...]
    scenarios: tuple[str, ...]
    anti_scenarios: tuple[str, ...]
    param_hints: tuple[tuple[str, str], ...]
    supports_signals: bool = False


STRATEGY_REGISTRY: dict[str, StrategyMeta] = {
    "AshareDoubleMaStrategy": StrategyMeta(
        class_name="AshareDoubleMaStrategy",
        title="A 股双均线",
        summary=("快均线上穿慢均线买入，下穿卖出。继承 AShareTemplate：仅做多、100 股整手、T+1 卖出。"),
        tags=("趋势跟踪", "日 K", "仅做多"),
        scenarios=(
            "均线趋势较明显的蓝筹或行业龙头",
            "中短期波段，能接受一定滞后",
            "已有本地日 K，先做单标的验证",
        ),
        anti_scenarios=(
            "长期横盘震荡（易反复金叉/死叉磨损）",
            "需要做空或日内 T+0 的场景",
            "极短周期或分钟级高频",
        ),
        param_hints=(
            ("fast_window", "快线周期，默认 10"),
            ("slow_window", "慢线周期，默认 20，需大于 fast_window"),
            ("trade_volume", "每次交易股数，100 的整数倍"),
        ),
        supports_signals=True,
    ),
    "AshareShortBreakoutStrategy": StrategyMeta(
        class_name="AshareShortBreakoutStrategy",
        title="A 股短线放量突破",
        summary=("收盘价突破近 N 日高点且量比放大、快线在慢线上方时买入；死叉/止损/止盈/持仓天数到期卖出。适合 1～5 日短线。"),
        tags=("短线", "突破", "日 K", "仅做多"),
        scenarios=(
            "活跃股、题材龙头，日 K 量能配合",
            "1～5 个交易日内了结",
            "能接受 T+1 隔日才能止损",
        ),
        anti_scenarios=(
            "低流动性、长期横盘",
            "追涨停后无法成交",
            "需要日内 T+0",
        ),
        param_hints=(
            ("fast_window", "快均线，默认 5"),
            ("slow_window", "慢均线，默认 10"),
            ("breakout_lookback", "突破回看天数，默认 5"),
            ("volume_ratio_min", "量比下限，默认 1.5"),
            ("stop_loss_pct", "止损比例，默认 0.03"),
            ("take_profit_pct", "止盈比例，默认 0.06"),
            ("max_hold_days", "最长持仓天数，默认 3"),
        ),
        supports_signals=True,
    ),
    "AshareSwingMaStrategy": StrategyMeta(
        class_name="AshareSwingMaStrategy",
        title="A 股波段回踩均线",
        summary=("金叉后不追高，等待缩量回踩慢均线再买入；死叉、跌破慢线或止损卖出。适合 1～4 周波段。"),
        tags=("波段", "回踩", "日 K", "仅做多"),
        scenarios=(
            "趋势明确的行业龙头或蓝筹",
            "愿意等待回踩、避免追涨",
            "持仓 1～4 周",
        ),
        anti_scenarios=(
            "V 型反转不给回踩机会",
            "长期阴跌无金叉",
            "需要高频交易",
        ),
        param_hints=(
            ("fast_window", "快均线，默认 10"),
            ("slow_window", "慢均线，默认 20"),
            ("pullback_pct", "回踩带宽（%），默认 2.0"),
            ("pullback_wait_days", "金叉后等待回踩天数，默认 5"),
            ("stop_loss_pct", "止损比例，默认 0.05"),
        ),
        supports_signals=True,
    ),
    "AshareTrendMaStrategy": StrategyMeta(
        class_name="AshareTrendMaStrategy",
        title="A 股趋势均线",
        summary=("MA 金叉且 ADX 高于阈值、价在慢线上方、慢线向上时买入；死叉、跌破慢线或追踪止损卖出。适合 1～6 月趋势。"),
        tags=("趋势", "ADX", "日 K", "仅做多"),
        scenarios=(
            "中期趋势明确的龙头或指数成分",
            "低频持仓，能接受滞后",
            "配合相对指数强度选股更佳",
        ),
        anti_scenarios=(
            "长期横盘 ADX 低于阈值",
            "慢线仍向下时金叉",
            "需要短线或日内交易",
        ),
        param_hints=(
            ("fast_window", "快均线，默认 20"),
            ("slow_window", "慢均线，默认 60"),
            ("adx_period", "ADX 周期，默认 14"),
            ("adx_threshold", "ADX 阈值，默认 25"),
            ("trailing_stop_pct", "追踪止损比例，默认 0.12"),
        ),
        supports_signals=True,
    ),
    "AshareLimitBoardStrategy": StrategyMeta(
        class_name="AshareLimitBoardStrategy",
        title="A 股极致短线·打板",
        summary=("涨停价触及与封板回封规则；日 K 回测 + limit_list_d 封板时间；一字板可过滤。"),
        tags=("极致短线", "打板", "日 K"),
        scenarios=("情绪启动–高潮", "龙头与核心跟风", "10cm 主板"),
        anti_scenarios=("退潮 / 冰点", "20cm 创科", "一字缩量板"),
        param_hints=(("seal_time_cutoff", "封板时间上限，默认 10:30"),),
        supports_signals=True,
    ),
    "AshareIntradayBreakoutStrategy": StrategyMeta(
        class_name="AshareIntradayBreakoutStrategy",
        title="A 股极致短线·半路",
        summary=("带量拉升突破关键位；日 K 涨幅 3–7% + 量比，快线在慢线上方确认。"),
        tags=("极致短线", "半路", "日 K"),
        scenarios=("题材发酵", "板块联动拉升", "20cm 弹性票"),
        anti_scenarios=("无量脉冲", "尾盘偷袭"),
        param_hints=(("min_change_pct", "最低涨幅，默认 3"), ("max_change_pct", "最高涨幅，默认 7")),
        supports_signals=True,
    ),
    "AsharePullbackStrategy": StrategyMeta(
        class_name="AsharePullbackStrategy",
        title="A 股极致短线·低吸",
        summary=("核心分歧回踩 MA5 或日内承接；日 K 缩量回踩 + 趋势过滤。"),
        tags=("极致短线", "低吸", "日 K"),
        scenarios=("分歧期核心票", "龙头炸板回踩", "MA5 附近承接"),
        anti_scenarios=("趋势破坏", "退潮期抄底"),
        param_hints=(("ma_window", "回踩均线，默认 5"),),
        supports_signals=True,
    ),
    "AshareOvernightExitStrategy": StrategyMeta(
        class_name="AshareOvernightExitStrategy",
        title="A 股隔日退出规则集",
        summary=("高开低走止损、隔日卖铁则等退出规则（MVP：行情字段 + 持仓 overlay）。"),
        tags=("极致短线", "退出", "持仓区"),
        scenarios=("持仓区绑定", "隔日计划执行"),
        anti_scenarios=("中线趋势持仓", "无分 K 数据时仅提示"),
        param_hints=(("stop_minutes", "开盘止损观察分钟，默认 30"),),
        supports_signals=False,
    ),
}

ULTRA_SHORT_STRATEGY_CLASS_NAMES: tuple[str, ...] = (
    "AshareLimitBoardStrategy",
    "AshareIntradayBreakoutStrategy",
    "AsharePullbackStrategy",
    "AshareOvernightExitStrategy",
)


def list_signal_strategy_metas() -> list[StrategyMeta]:
    """返回支持自选信号计算的已注册策略元数据。"""
    return [meta for meta in STRATEGY_REGISTRY.values() if meta.supports_signals]


def list_ultra_short_strategy_metas() -> list[StrategyMeta]:
    """S-01：极致短线策略族元数据（含规划项）。"""
    return [STRATEGY_REGISTRY[name] for name in ULTRA_SHORT_STRATEGY_CLASS_NAMES if name in STRATEGY_REGISTRY]


def get_strategy_meta(class_name: str) -> StrategyMeta | None:
    return STRATEGY_REGISTRY.get(class_name)


def format_strategy_guide(meta: StrategyMeta, *, tokens=None) -> str:
    """渲染策略说明（HTML，供 QLabel RichText 使用）。"""
    from vnpy_common.ui.theme.html_palette import html_palette
    from vnpy_common.ui.theme.manager import theme_manager

    colors = html_palette(tokens or theme_manager().tokens())
    tags = " · ".join(meta.tags)
    scenarios = "".join(f"<li>{item}</li>" for item in meta.scenarios)
    anti = "".join(f"<li>{item}</li>" for item in meta.anti_scenarios)
    params = "".join(f"<li><code>{name}</code>：{hint}</li>" for name, hint in meta.param_hints)
    return (
        f'<p style="margin:0 0 6px 0;"><b>{meta.title}</b>'
        f'<span style="color:{colors.label};"> · {tags}</span></p>'
        f'<p style="margin:0 0 8px 0;color:{colors.body};">{meta.summary}</p>'
        f'<p style="margin:0 0 4px 0;color:{colors.section};">适用</p>'
        f"<ul style='margin:0 0 8px 16px;padding:0;'>{scenarios}</ul>"
        f'<p style="margin:0 0 4px 0;color:{colors.warning};">不适用</p>'
        f"<ul style='margin:0 0 8px 16px;padding:0;'>{anti}</ul>"
        f'<p style="margin:0 0 4px 0;color:{colors.label};">关键参数</p>'
        f"<ul style='margin:0 0 0 16px;padding:0;'>{params}</ul>"
        f'<p style="margin:8px 0 0 0;color:{colors.muted};font-size:11px;">'
        "请选用 Ashare* 策略，勿选 vnpy 内置含做空逻辑的策略。"
        "</p>"
    )


def format_missing_strategy_guide(class_name: str, *, tokens=None) -> str:
    from vnpy_common.ui.theme.html_palette import html_palette
    from vnpy_common.ui.theme.manager import theme_manager

    colors = html_palette(tokens or theme_manager().tokens())
    return f'<p style="color:{colors.label};">暂无 <code>{class_name}</code> 的说明，可在 <code>strategies/registry.py</code> 补充。</p>'
