"""交易体系 Playbook 服务。"""

from __future__ import annotations

from typing import cast

from vnpy.trader.engine import MainEngine

from vnpy_ashare.config.playbook_templates.defaults import _TEMPLATE_BUILDERS, playbook_template_sections
from vnpy_ashare.config.preferences.strategy_profile import (
    StrategyProfileId,
    get_strategy_profile,
    load_strategy_profile_id,
)
from vnpy_ashare.domain.time.market_hours import ashare_market_phase_label
from vnpy_ashare.domain.trading.playbook import DisciplineCheckItem, HomePlaybookStatus, PlaybookSection
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.screener.hard_filter_prefs import (
    STRATEGY_PROFILE_HARD_FILTER_PRESET,
    load_hard_filter_prefs,
)
from vnpy_ashare.storage.connection import get_meta, set_meta
from vnpy_ashare.storage.repositories.positions import load_position_rows
from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan
from vnpy_ashare.storage.repositories.trading_playbook import (
    count_playbook_sections,
    list_playbook_sections,
    upsert_playbook_sections,
)
from vnpy_ashare.storage.repositories.trading_playbook_discipline import load_discipline_checks
from vnpy_ashare.trading.plan.off_plan import list_off_plan_position_vt_symbols
from vnpy_ashare.trading.risk.book_pnl import summarize_book_pnl
from vnpy_ashare.trading.risk.metrics import format_emotion_position_hint
from vnpy_ashare.trading.risk.realized_pnl import today_trade_date

_META_SEED_KEY = "playbook_seeded_profile"


def load_playbook_seeded_profile() -> StrategyProfileId:
    raw = get_meta(_META_SEED_KEY)
    if raw in _TEMPLATE_BUILDERS:
        return cast(StrategyProfileId, raw)
    return load_strategy_profile_id()


def touch_playbook_seeded_profile(profile_id: StrategyProfileId) -> None:
    set_meta(_META_SEED_KEY, profile_id)


def _template_body_map(profile_id: StrategyProfileId) -> dict[str, str]:
    return {section.section_id: section.body_md.strip() for section in playbook_template_sections(profile_id)}


def list_playbook_merge_candidate_sections(
    from_profile_id: StrategyProfileId,
    to_profile_id: StrategyProfileId,
) -> tuple[str, ...]:
    """仍为旧 Profile 默认模板、且与新 Profile 模板正文不同的章节。"""
    if from_profile_id == to_profile_id:
        return ()
    from_bodies = _template_body_map(from_profile_id)
    to_bodies = _template_body_map(to_profile_id)
    candidates: list[str] = []
    for section in list_playbook_sections():
        section_id = section.section_id
        if section_id not in from_bodies or section_id not in to_bodies:
            continue
        if section.body_md.strip() != from_bodies[section_id]:
            continue
        if from_bodies[section_id] == to_bodies[section_id]:
            continue
        candidates.append(section_id)
    return tuple(candidates)


def apply_playbook_template_merge(
    profile_id: StrategyProfileId,
    section_ids: tuple[str, ...],
) -> None:
    """将指定章节替换为新 Profile 模板（保留折叠状态与排序）。"""
    if not section_ids:
        touch_playbook_seeded_profile(profile_id)
        return
    current = {item.section_id: item for item in list_playbook_sections()}
    templates = {item.section_id: item for item in playbook_template_sections(profile_id)}
    updates: list[PlaybookSection] = []
    for section_id in section_ids:
        template = templates.get(section_id)
        if template is None:
            continue
        existing = current.get(section_id)
        updates.append(
            PlaybookSection(
                section_id=section_id,
                title=template.title,
                body_md=template.body_md,
                collapsed=existing.collapsed if existing is not None else template.collapsed,
                sort_order=existing.sort_order if existing is not None else template.sort_order,
            ),
        )
    if updates:
        upsert_playbook_sections(tuple(updates))
    touch_playbook_seeded_profile(profile_id)


def ensure_playbook_seeded() -> None:
    profile_id = load_strategy_profile_id()
    if count_playbook_sections() > 0:
        return
    sections = playbook_template_sections(profile_id)
    upsert_playbook_sections(sections)
    touch_playbook_seeded_profile(profile_id)


def load_playbook_sections() -> tuple[PlaybookSection, ...]:
    ensure_playbook_seeded()
    return list_playbook_sections()


def build_mirror_appendix(section_id: str) -> str:
    if section_id == "universe":
        profile = get_strategy_profile(load_strategy_profile_id())
        prefs = load_hard_filter_prefs()
        preset = STRATEGY_PROFILE_HARD_FILTER_PRESET.get(profile.profile_id, "balanced")
        flags = []
        if prefs.exclude_st:
            flags.append("ST✗")
        if prefs.exclude_suspended:
            flags.append("停牌✗")
        if prefs.exclude_one_word:
            flags.append("一字板✗")
        if prefs.exclude_limit_board:
            flags.append("连板✗")
        boards = prefs.allowed_market_boards or "全板块"
        return (
            "\n\n---\n\n**当前配置镜像（只读）**\n\n"
            f"- Profile：**{profile.title}**（`{profile.signal_class_name}`）\n"
            f"- 硬过滤模板：**{preset}** · 最低成交额 {prefs.min_amount_wan:.0f} 万 · 最低市值 {prefs.min_total_mv_yi:.0f} 亿\n"
            f"- 开关：{' · '.join(flags) if flags else '无额外排除'}\n"
            f"- 板块：{boards}\n"
        )
    if section_id == "risk":
        return ""
    return ""


def render_section_markdown(section: PlaybookSection) -> str:
    appendix = build_mirror_appendix(section.section_id)
    body = section.body_md.strip()
    if appendix:
        return f"{body}{appendix}"
    return body


def load_discipline_checklist(trade_date: str | None = None) -> tuple[DisciplineCheckItem, ...]:
    day = (trade_date or today_trade_date())[:10]
    return load_discipline_checks(day)


def _resolve_home_daily_pnl_pct() -> float | None:
    """首屏只读：持仓浮盈占比（无持仓时返回 None）。"""
    book = summarize_book_pnl({})
    if book.total_float_pnl_pct is not None:
        return book.total_float_pnl_pct
    return book.combined_pnl_pct


def _format_home_daily_pnl_text(daily_pct: float | None) -> str:
    if daily_pct is not None:
        return f"{daily_pct:+.2f}%"
    return "—"


def build_home_playbook_status(main_engine: MainEngine | None) -> HomePlaybookStatus:
    day = today_trade_date()
    profile = get_strategy_profile(load_strategy_profile_id())
    daily_pct = _resolve_home_daily_pnl_pct()
    daily_text = _format_home_daily_pnl_text(daily_pct)

    emotion = load_emotion_cycle_snapshot(fetch_if_missing=False)
    emotion_label = emotion.stage_label if emotion is not None else "—"
    pos_hint = (
        format_emotion_position_hint(
            position_pct_min=emotion.position_pct_min if emotion is not None else None,
            position_pct_max=emotion.position_pct_max if emotion is not None else None,
        )
        or "—"
    )
    allow_new = emotion.allow_new_positions if emotion is not None else True

    position_vts = {f"{row.get('symbol')}.{row.get('exchange')}" for row in load_position_rows() if row.get("symbol") and row.get("exchange")}
    position_count = len(position_vts)

    plan = load_active_trading_plan(day)
    if plan is None:
        plan_text = "今日无 active 计划"
    else:
        on_plan_held = sum(1 for vt in plan.watchlist_vt_symbols if vt in position_vts)
        plan_text = f"计划 {on_plan_held}/{len(plan.symbols)} 已持仓 · 上限 {plan.max_position_pct:.0f}%"

    off_plan = list_off_plan_position_vt_symbols(trade_date=day)
    if off_plan:
        position_text = f"{position_count} 笔 · 计划外 {len(off_plan)}"
    else:
        position_text = f"{position_count} 笔持仓"

    checks = load_discipline_checks(day)
    done = sum(1 for item in checks if item.checked)
    discipline_progress = f"纪律 {done}/{len(checks)}" if checks else ""

    alerts: list[str] = []
    if emotion is not None and emotion.stage in {"recession", "divergence", "ice"}:
        alerts.append("情绪阶段偏保守，请对照 §1 择时")
    elif emotion is not None and not emotion.allow_new_positions:
        alerts.append("当前环境不建议新开仓")
    if off_plan:
        preview = "、".join(off_plan[:3])
        suffix = "…" if len(off_plan) > 3 else ""
        alerts.append(f"计划外持仓：{preview}{suffix}")

    return HomePlaybookStatus(
        profile_title=profile.title,
        phase_label=ashare_market_phase_label(),
        emotion_label=emotion_label,
        emotion_position_hint=pos_hint,
        allow_new_positions=allow_new,
        daily_pnl_text=daily_text,
        plan_text=plan_text,
        position_text=position_text,
        discipline_progress=discipline_progress,
        off_plan_symbols=off_plan,
        alert="；".join(alerts),
    )
