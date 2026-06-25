"""自选页（无选中个股）AI 快捷动作。"""

from __future__ import annotations

from vnpy_ashare.ai.context.market_overview import build_intraday_environment_prompt
from vnpy_ashare.ai.context.screening_actions import build_interpret_screen_action
from vnpy_common.ai.protocol import QuickAction


def build_watchlist_portfolio_prompt() -> str:
    return (
        "请结合持仓记账与自选池，复盘整体仓位与隔日风险："
        "哪些持仓浮盈/浮亏突出、是否偏离交易计划、今日需遵守的纪律要点。"
        "须调用相关工具核对，不要编造持仓或行情数据。"
    )


def build_watchlist_page_quick_actions() -> list[QuickAction]:
    actions: list[QuickAction] = [
        QuickAction(
            id="watchlist_portfolio",
            label="持仓复盘",
            tooltip="自选池 + 记账持仓的整体风险复盘",
            prompt=build_watchlist_portfolio_prompt(),
        ),
        QuickAction(
            id="watchlist_intraday_env",
            label="今日短线环境",
            tooltip="评估极致短线是否可做、连板结构与仓位建议",
            prompt=build_intraday_environment_prompt(),
        ),
    ]
    interpret = build_interpret_screen_action()
    if interpret is not None:
        actions.append(interpret)
    return actions
