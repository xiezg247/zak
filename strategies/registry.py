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
    ),
}


def get_strategy_meta(class_name: str) -> StrategyMeta | None:
    return STRATEGY_REGISTRY.get(class_name)


def format_strategy_guide(meta: StrategyMeta) -> str:
    """渲染策略说明（HTML，供 QLabel RichText 使用）。"""
    tags = " · ".join(meta.tags)
    scenarios = "".join(f"<li>{item}</li>" for item in meta.scenarios)
    anti = "".join(f"<li>{item}</li>" for item in meta.anti_scenarios)
    params = "".join(f"<li><code>{name}</code>：{hint}</li>" for name, hint in meta.param_hints)
    return (
        f'<p style="margin:0 0 6px 0;"><b>{meta.title}</b>'
        f'<span style="color:#8a8a8a;"> · {tags}</span></p>'
        f'<p style="margin:0 0 8px 0;color:#c8c8c8;">{meta.summary}</p>'
        f'<p style="margin:0 0 4px 0;color:#4a9eff;">适用</p>'
        f"<ul style='margin:0 0 8px 16px;padding:0;'>{scenarios}</ul>"
        f'<p style="margin:0 0 4px 0;color:#f0b429;">不适用</p>'
        f"<ul style='margin:0 0 8px 16px;padding:0;'>{anti}</ul>"
        f'<p style="margin:0 0 4px 0;color:#8a8a8a;">关键参数</p>'
        f"<ul style='margin:0 0 0 16px;padding:0;'>{params}</ul>"
        '<p style="margin:8px 0 0 0;color:#6a6a6a;font-size:11px;">'
        "请选用 Ashare* 策略，勿选 vnpy 内置含做空逻辑的策略。"
        "</p>"
    )


def format_missing_strategy_guide(class_name: str) -> str:
    return f'<p style="color:#8a8a8a;">暂无 <code>{class_name}</code> 的说明，可在 <code>strategies/registry.py</code> 补充。</p>'
