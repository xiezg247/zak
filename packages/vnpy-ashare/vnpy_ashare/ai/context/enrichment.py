"""AI 上下文增强：badge、chip_text、快捷动作（供 Service 写入前调用）。"""

from __future__ import annotations

import re

from vnpy_ashare.ai.context.backtest import build_backtest_page_quick_actions, build_batch_compare_quick_actions
from vnpy_ashare.ai.context.feed import build_feed_page_quick_actions
from vnpy_ashare.ai.context.market_overview import build_market_page_quick_actions, format_market_overview_extra
from vnpy_ashare.ai.context.playbook import build_playbook_page_quick_actions
from vnpy_ashare.ai.context.quote.assembly import build_assistant_quick_actions, build_assistant_screening_menus, build_floating_stock_quick_actions
from vnpy_ashare.ai.context.radar import build_radar_page_quick_actions
from vnpy_ashare.ai.context.screening_actions import build_interpret_screen_action, build_screener_hub_quick_actions
from vnpy_ashare.ai.context.sector_flow import build_sector_flow_page_quick_actions
from vnpy_ashare.ai.context.store import get_screening_results
from vnpy_ashare.ai.context.watchlist import build_watchlist_page_quick_actions
from vnpy_ashare.quotes.radar.radar_board_store import get_radar_board_snapshot
from vnpy_common.ai.protocol import AiContextData, QuickAction


def build_context_quick_actions(data: AiContextData) -> list[QuickAction]:
    """按页面与选中标的组装快捷动作（与 enrich 路由一致）。"""
    return _build_actions(data)


def enrich_context_with_actions(data: AiContextData) -> AiContextData:
    """为上下文填充 badge、chip_text、actions。"""
    badge = _build_badge(data)
    chip_text = _build_chip_text(data)
    actions = _build_actions(data)
    return data.model_copy(update={"badge": badge, "chip_text": chip_text, "actions": actions})


def build_screening_quick_actions() -> list[QuickAction]:
    """选股页：解读最近结果 + Hub 雷达入口 + 形态/条件选股菜单。"""
    actions: list[QuickAction] = []
    interpret = build_interpret_screen_action()
    if interpret is not None:
        actions.append(interpret)
    actions.extend(build_screener_hub_quick_actions())
    actions.extend(build_assistant_screening_menus())
    return actions


def build_assistant_panel_quick_actions() -> list[QuickAction]:
    """全屏 AI 助手：最近结果解读 + 单票分析 + 全市场选股菜单。"""
    actions: list[QuickAction] = []
    interpret = build_interpret_screen_action()
    if interpret is not None:
        actions.append(interpret)
    actions.extend(build_assistant_quick_actions())
    return actions


def build_page_quick_actions(data: AiContextData) -> list[QuickAction]:
    """按页面类型组装非个股快捷动作。"""
    if data.page == "守则":
        return build_playbook_page_quick_actions()
    if data.page == "信息流":
        return build_feed_page_quick_actions()
    if data.page == "选股":
        return build_screening_quick_actions()
    if data.page == "板块资金":
        return build_sector_flow_page_quick_actions()
    if data.page == "策略回测":
        return build_backtest_page_quick_actions()
    if data.page == "回测对比":
        return build_batch_compare_quick_actions()
    if data.page == "自选":
        return build_watchlist_page_quick_actions()
    if data.page == "数据管理":
        return [
            QuickAction(
                id="data_gap",
                label="检查数据缺口",
                prompt=("请根据当前本地 K 线覆盖情况，分析可能存在的数据缺口，并说明建议优先补全哪些标的或周期。"),
            ),
        ]
    return []


def _build_actions(data: AiContextData) -> list[QuickAction]:
    if data.page == "守则":
        return build_playbook_page_quick_actions()
    if data.page == "信息流":
        return build_feed_page_quick_actions()
    if data.page == "雷达" and not data.symbol:
        return build_radar_page_quick_actions()
    if data.page == "市场":
        compact = bool(data.symbol)
        actions = build_market_page_quick_actions(compact=compact)
        if data.symbol:
            actions.extend(
                build_floating_stock_quick_actions(
                    data.symbol,
                    exchange_cn=data.exchange,
                    name=data.name,
                    page=data.page,
                    extra=data.extra,
                )
            )
        return actions
    if data.page == "雷达" and data.symbol:
        actions = build_radar_page_quick_actions(compact=True)
        actions.extend(
            build_floating_stock_quick_actions(
                data.symbol,
                exchange_cn=data.exchange,
                name=data.name,
                page=data.page,
                extra=data.extra,
            )
        )
        return actions
    if data.page in ("策略回测", "回测对比", "板块资金"):
        return build_page_quick_actions(data)
    if data.page == "自选" and not data.symbol:
        return build_watchlist_page_quick_actions()
    if data.page in ("自选", "本地") and data.symbol:
        return build_floating_stock_quick_actions(
            data.symbol,
            exchange_cn=data.exchange,
            name=data.name,
            page=data.page,
            extra=data.extra,
        )
    return build_page_quick_actions(data)


def _build_badge(data: AiContextData) -> str:
    if data.page == "选股":
        ctx = get_screening_results()
        if ctx is not None and ctx.count > 0:
            return f"选股·{ctx.count}"
        return "选股"
    if data.page in ("自选", "市场", "雷达", "本地", "数据管理", "守则", "信息流", "板块资金", "策略回测", "回测对比"):
        if data.page == "雷达":
            snapshot = get_radar_board_snapshot()
            if snapshot is not None and snapshot.resonance_count > 0:
                return f"雷达·{snapshot.resonance_count}"
        return data.page[:2] if data.page == "数据管理" else data.page
    if data.page:
        return data.page[:2]
    return ""


def _build_chip_text(data: AiContextData) -> str:
    parts: list[str] = []
    if data.page == "市场":
        overview = format_market_overview_extra()
        if overview:
            first_line = overview.splitlines()[0]
            parts.append(first_line.replace("【大盘概览】", "大盘").strip())
    if data.page:
        parts.append(data.page)
    if data.symbol and data.exchange:
        title = data.name or data.symbol
        parts.append(title)
        change = _extract_change_pct(data.quote_summary)
        if change:
            parts.append(change)
    elif data.page == "选股":
        ctx = get_screening_results()
        if ctx is not None and ctx.count > 0:
            parts.append(f"命中 {ctx.count} 条")
        else:
            parts.append("暂无结果")
    elif data.page == "雷达":
        snapshot = get_radar_board_snapshot()
        if snapshot is not None and snapshot.resonance_count > 0:
            parts.append(f"共振 {snapshot.resonance_count} 只")
        else:
            parts.append("暂无共振")
    elif data.page == "板块资金" and data.extra:
        flow_hint = _sector_flow_chip_hint(data.extra)
        if flow_hint:
            parts.append(flow_hint)
    elif data.page == "策略回测" and data.extra:
        form_hint = _backtest_form_chip_hint(data.extra)
        if form_hint:
            parts.append(form_hint)
    elif data.page == "回测对比" and data.extra:
        batch_hint = _batch_compare_chip_hint(data.extra)
        if batch_hint:
            parts.append(batch_hint)
    elif data.page == "自选" and not data.symbol:
        parts.append("未选中个股")
    elif data.page == "数据管理" and data.extra:
        first_line = data.extra.splitlines()[1] if "\n" in data.extra else data.extra
        parts.append(first_line.replace("日线：", "").split("，")[0] if "日线" in first_line else "本地数据")
    return " · ".join(parts) if parts else "AI 助手"


def _extract_change_pct(quote_summary: str) -> str:
    if not quote_summary:
        return ""
    match = re.search(r"（([+-][\d.]+%)）", quote_summary)
    return match.group(1) if match else ""


def _sector_flow_chip_hint(extra: str) -> str:
    for line in extra.splitlines():
        if "净流入" in line and "净流出" in line:
            inflow = line.split("；", 1)[0].strip()
            return inflow.replace("净流入 ", "流入 ")
    return ""


def _backtest_form_chip_hint(extra: str) -> str:
    for line in extra.splitlines():
        if line.startswith("当前表单："):
            return line.removeprefix("当前表单：").strip()
        if line.startswith("最近回测摘要："):
            break
    for line in extra.splitlines():
        if line.strip().startswith("策略："):
            return line.strip()
    return "待回测"


def _batch_compare_chip_hint(extra: str) -> str:
    for line in extra.splitlines():
        if line.startswith("当前批次："):
            return line.removeprefix("当前批次：").strip()
    return ""
