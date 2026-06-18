"""通知消息正文模板。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.notifications.core.events import (
    NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
    NOTIFY_EVENT_JOURNAL_VIOLATION,
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_POSITION_ALERT,
    NOTIFY_EVENT_RADAR_LEADER_READY,
    NOTIFY_EVENT_RISK_GATE_CHANGE,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
)


def _now_text() -> str:
    return format_china_datetime()


def format_notify_text(event_id: str, payload: dict[str, Any]) -> str:
    now = _now_text()
    if event_id == NOTIFY_EVENT_MANUAL_TEST:
        return f"【zak】测试消息\n飞书 Webhook 配置正常\n时间 {now}"

    if event_id == NOTIFY_EVENT_SCREENER_INTRADAY_DONE:
        return _format_screener_done("盘中选股完成", payload, now)

    if event_id == NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE:
        return _format_screener_done("盘后选股完成", payload, now)

    if event_id == NOTIFY_EVENT_SCHEDULER_JOB_FAILED:
        job_name = str(payload.get("job_name") or payload.get("job_id") or "未知任务")
        job_id = str(payload.get("job_id") or "")
        message = str(payload.get("message") or "").strip()
        lines = ["【zak】定时任务失败", f"任务 {job_name}"]
        if job_id and job_id != job_name:
            lines.append(f"ID {job_id}")
        if message:
            lines.append(message)
        lines.append(f"时间 {now}")
        return "\n".join(lines)

    if event_id == NOTIFY_EVENT_EMOTION_STAGE_CHANGE:
        stage_label = str(payload.get("stage_label") or payload.get("stage") or "")
        limit_up = payload.get("limit_up_count")
        limit_down = payload.get("limit_down_count")
        pos_max = payload.get("position_pct_max")
        lines = [f"【zak】情绪阶段 → {stage_label}"]
        if limit_up is not None and limit_down is not None:
            lines.append(f"涨停 {limit_up} · 跌停 {limit_down}")
        if pos_max is not None:
            lines.append(f"建议总仓位 ≤ {int(float(pos_max) * 100)}%")
        if not payload.get("allow_new_positions", True):
            lines.append("建议：不开新仓（规则参考，非投资建议）")
        lines.append(f"时间 {now}")
        return "\n".join(lines)

    if event_id == NOTIFY_EVENT_RISK_GATE_CHANGE:
        state_label = str(payload.get("state_label") or payload.get("state") or "")
        lines = [f"【zak】风控状态 → {state_label}"]
        for warning in payload.get("warnings") or ():
            lines.append(str(warning))
        daily = payload.get("daily_pnl_pct")
        if daily is not None:
            lines.append(f"当日盈亏合计 {daily:.1f}%")
        lines.append("请复盘后再操作")
        lines.append(f"时间 {now}")
        return "\n".join(lines)

    if event_id == NOTIFY_EVENT_POSITION_ALERT:
        name = str(payload.get("name") or "")
        symbol = str(payload.get("symbol") or "")
        reasons = str(payload.get("reasons") or "")
        pnl = payload.get("pnl_pct")
        exit_signal = str(payload.get("exit_signal") or "")
        t1_locked = payload.get("t1_locked")
        lines = ["【zak】持仓提醒", f"{name} {symbol}".strip()]
        if reasons:
            lines.append(f"标签：{reasons}")
        if pnl is not None:
            lines.append(f"浮盈 {float(pnl):+.1f}%")
        if exit_signal:
            lines.append(f"退出信号：{exit_signal}")
        if t1_locked is not None:
            lines.append(f"T+1：{'锁定' if t1_locked else '可卖'}")
        lines.append(f"时间 {now}")
        return "\n".join(lines)

    if event_id == NOTIFY_EVENT_JOURNAL_VIOLATION:
        name = str(payload.get("symbol") or "")
        exchange = str(payload.get("exchange") or "")
        side = str(payload.get("side") or "")
        tags = str(payload.get("violation_tags") or "")
        reason = str(payload.get("reason") or "").strip()
        emotion = str(payload.get("emotion_stage") or "").strip()
        side_label = {"buy": "买入", "sell": "卖出", "hold": "持有"}.get(side, side)
        lines = ["【zak】交易纪律提醒", f"{name}.{exchange} · {side_label}"]
        if tags:
            lines.append(f"违规：{tags}")
        if emotion:
            lines.append(f"情绪阶段：{emotion}")
        if reason:
            lines.append(reason)
        lines.append(f"时间 {now}")
        return "\n".join(lines)

    if event_id == NOTIFY_EVENT_RADAR_LEADER_READY:
        return _format_radar_leader_ready(payload, now)

    msg = f"unknown event: {event_id}"
    raise ValueError(msg)


def _format_screener_done(title: str, payload: dict[str, Any], now: str) -> str:
    message = str(payload.get("message") or "").strip()
    recipe = str(payload.get("recipe") or "").strip()
    hit_count = payload.get("hit_count")
    lines = [f"【zak】{title}"]
    if recipe:
        lines.append(f"配方 {recipe}")
    if hit_count is not None:
        lines.append(f"命中 {hit_count} 条")
    if message:
        lines.append(message)
    lines.append(f"时间 {now}")
    lines.append("打开客户端查看选股 Hub 运行历史")
    return "\n".join(lines)


def _format_radar_leader_ready(payload: dict[str, Any], now: str) -> str:
    condition = str(payload.get("condition") or "雷达龙头").strip()
    hit_count = payload.get("hit_count")
    top_name = str(payload.get("top_name") or "").strip()
    top_symbol = str(payload.get("top_symbol") or "").strip()
    top_score = payload.get("top_score")
    tier_label = str(payload.get("top_tier_label") or "").strip()
    sector = str(payload.get("sector_name") or "").strip()
    variant = str(payload.get("variant") or "").strip()
    lines = ["【zak】龙头池更新", condition]
    if variant:
        lines.append(f"模式 {variant}")
    if hit_count is not None:
        lines.append(f"命中 {hit_count} 条")
    leader_line = " · ".join(part for part in (top_name, top_symbol, tier_label) if part)
    if leader_line:
        lines.append(f"龙一 {leader_line}")
    if top_score is not None:
        lines.append(f"评分 {float(top_score):.0f}")
    if sector:
        lines.append(f"主线 {sector}")
    lines.append(f"时间 {now}")
    lines.append("打开选股 Hub 查看龙头列表")
    return "\n".join(lines)
