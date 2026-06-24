"""雷达 AI 预填文案生成。"""

from __future__ import annotations

from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.quotes.radar.loaders.resonance import (
    compute_radar_resonance,
    compute_radar_resonance_scores,
)
from vnpy_ashare.quotes.radar.radar_horizon import build_outlook_ai_prompt
from vnpy_ashare.quotes.radar.radar_horizon_predict import build_predict_ai_prompt
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow

EOD_LEADER_CARD_IDS = ("leader_pick", "discovery_limit_ladder", "sector_theme")


def row_ai_summary(row: RadarRow) -> str:
    price = f"{row.price:.2f}" if row.price is not None else "—"
    change = f"{row.change_pct:+.2f}%" if row.change_pct is not None else "—"
    return f"{row.name}({row.symbol}) 现价{price} {change} · {row.metric_label} {row.metric_value} · {row.sub_label} {row.sub_value}"


def build_radar_card_ai_prompt(
    card_id: str,
    data: RadarCardData,
    *,
    resonance_counts: dict[str, int] | None = None,
) -> str:
    """生成单张雷达卡的 AI 解读预填文案。"""
    if not data.rows and not data.empty_message:
        return ""
    counts = resonance_counts or {}
    lines = [
        f"请解读雷达卡片「{data.title}」：",
        "1. 概括本卡核心结论与优先顺序",
        "2. 标注共振标的（若有多卡重复出现）",
        "3. 不要编造未出现在数据中的价格或指标",
        "",
    ]
    if data.subtitle:
        lines.append(data.subtitle)
    if data.ai_hint:
        lines.append(data.ai_hint)
    lines.append("")
    if not data.rows:
        lines.append(data.empty_message or "（暂无数据）")
        return "\n".join(lines).strip()

    if card_id == "watchlist_intraday":
        lines[0] = "请解读雷达「自选·异动」：关注自选池内波动、信号跃迁与 5 日统计情景（非价格预测）。"
    elif card_id == "sector_theme":
        lines[0] = "请解读雷达「板块·主线」：归纳今日行业轮动与龙头特征。"
    elif card_id in ("outlook_watch", "outlook_hold", "outlook_scenario"):
        single = build_outlook_ai_prompt({card_id: data}, card_id=card_id)
        return single or "\n".join(lines).strip()
    elif card_id == "outlook_predict":
        return build_predict_ai_prompt(data)

    for row in data.rows:
        marker = "★ " if counts.get(row.vt_symbol, 0) >= 2 else ""
        lines.append(f"- {marker}{row_ai_summary(row)}")
    return "\n".join(lines).strip()


def build_radar_ai_prompt(
    payload: dict[str, RadarCardData],
) -> str:
    """生成雷达页 AI 洞察预填文案。"""
    lines = [
        "请基于以下雷达页快照，给出今日 A 股洞察摘要：",
        "1. 市场主线与热点方向（参考板块·主线卡）",
        "2. 选股结果与发现/自选异动的交集（共振标的优先）",
        "3. 未来关注/可持/情景/预测卡基于策略或统计基线（约 5 日），非价格预测",
        "4. 建议重点关注的 3～5 只标的及理由",
        "5. 不要编造未出现在数据中的价格或指标",
        "",
    ]
    resonance = compute_radar_resonance(payload)
    resonance_scores = compute_radar_resonance_scores(payload)
    if resonance:
        parts: list[str] = []
        for vt_symbol, count in sorted(
            resonance_scores.items(),
            key=lambda item: (-item[1], -resonance.get(item[0], 0), item[0]),
        ):
            item = parse_stock_symbol(vt_symbol)
            label = item.name if item and item.name else vt_symbol
            score = resonance_scores.get(vt_symbol, 0.0)
            parts.append(f"{label}({count}卡·{score:.1f}分)")
        lines.append(f"共振标的：{', '.join(parts)}")
        lines.append("")
    for data in payload.values():
        lines.append(f"## {data.title}")
        if data.subtitle:
            lines.append(data.subtitle)
        if data.updated_at:
            lines.append(f"更新：{data.updated_at}")
        if not data.rows:
            lines.append(data.empty_message or "（暂无数据）")
        else:
            for row in data.rows:
                marker = "★ " if row.vt_symbol in resonance else ""
                lines.append(f"- {marker}{row_ai_summary(row)}")
        lines.append("")
    for outlook_card_id in ("outlook_watch", "outlook_hold", "outlook_scenario"):
        outlook_prompt = build_outlook_ai_prompt(payload, card_id=outlook_card_id)
        if outlook_prompt:
            lines.append("---")
            lines.append(outlook_prompt)
    predict_data = payload.get("outlook_predict")
    if predict_data is not None:
        predict_prompt = build_predict_ai_prompt(predict_data)
        if predict_prompt:
            lines.append("---")
            lines.append(predict_prompt)
    return "\n".join(lines).strip()


def build_eod_leader_prompt(payload: dict[str, RadarCardData]) -> str:
    """盘后专用：今日龙头结构 + 明日观察（P1-3）。"""
    from vnpy_ashare.quotes.market.emotion_cycle import format_mode_label, load_emotion_cycle_snapshot

    lines = [
        "请基于以下盘后雷达快照，完成「今日龙头结构 + 明日观察」复盘：",
        "1. 归纳今日龙头梯队：龙一/龙二/跟风、连板高度与板块主线",
        "2. 结合当前情绪阶段，给出明日总仓位区间与允许的买点模式（打板/半路/低吸）",
        "3. 列出 3～5 只明日观察标的及预设买卖条件（仅规则描述，不给具体买卖价）",
        "4. 退潮/冰点须明确不宜短线新开仓",
        "5. 不要编造未出现在数据中的价格或指标",
        "",
    ]
    cycle = load_emotion_cycle_snapshot(fetch_if_missing=True)
    if cycle is not None:
        pos_lo = int(round(cycle.position_pct_min * 100))
        pos_hi = int(round(cycle.position_pct_max * 100))
        lines.append(f"情绪周期：{cycle.stage_label} · 建议仓位 {pos_lo}–{pos_hi}% · 系数 {cycle.position_factor:.2f}")
        if cycle.allowed_modes:
            mode_text = "、".join(format_mode_label(mode) for mode in cycle.allowed_modes)
            lines.append(f"允许模式：{mode_text}")
        if cycle.warnings:
            lines.append(f"环境提示：{'；'.join(cycle.warnings)}")
        lines.append(f"盘面输入：涨停 {cycle.limit_up_count} · 跌停 {cycle.limit_down_count} · 最高连板 {cycle.inputs.get('max_limit_times', 0)}")
        lines.append("")

    resonance = compute_radar_resonance(payload)
    resonance_scores = compute_radar_resonance_scores(payload)
    if resonance:
        parts: list[str] = []
        for vt_symbol, count in sorted(
            resonance_scores.items(),
            key=lambda item: (-item[1], -resonance.get(item[0], 0), item[0]),
        )[:8]:
            item = parse_stock_symbol(vt_symbol)
            label = item.name if item and item.name else vt_symbol
            score = resonance_scores.get(vt_symbol, 0.0)
            parts.append(f"{label}({count}卡·{score:.1f}分)")
        lines.append(f"共振前列：{', '.join(parts)}")
        lines.append("")

    for card_id in EOD_LEADER_CARD_IDS:
        data = payload.get(card_id)
        if data is None:
            continue
        lines.append(f"## {data.title}")
        if data.subtitle:
            lines.append(data.subtitle)
        if data.updated_at:
            lines.append(f"更新：{data.updated_at}")
        if not data.rows:
            lines.append(data.empty_message or "（暂无数据）")
        else:
            for row in data.rows[:15]:
                marker = "★ " if row.vt_symbol in resonance else ""
                tier = f" [{row.leader_tier}]" if row.leader_tier else ""
                lines.append(f"- {marker}{row_ai_summary(row)}{tier}")
        lines.append("")

    has_focus_data = any((data := payload.get(card_id)) is not None and bool(data.rows) for card_id in EOD_LEADER_CARD_IDS)
    if not has_focus_data and not resonance:
        return ""
    return "\n".join(lines).strip()
