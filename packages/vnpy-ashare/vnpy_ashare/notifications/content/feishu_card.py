"""飞书 interactive 卡片构建（N-06）。"""

from __future__ import annotations

import os
from typing import Any

from vnpy_ashare.notifications.content.formatters import format_notify_text
from vnpy_ashare.notifications.core.events import (
    NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_POSITION_ALERT,
    NOTIFY_EVENT_RADAR_LEADER_READY,
    NOTIFY_EVENT_RISK_GATE_CHANGE,
    NOTIFY_EVENT_SCHEDULER_JOB_FAILED,
    NOTIFY_EVENT_SCREENER_INTRADAY_DONE,
    NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE,
)


def notify_open_url() -> str:
    return os.environ.get("NOTIFY_OPEN_URL", "").strip()


def build_feishu_interactive_card(event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """由事件 payload 构建飞书 interactive 卡片 body（不含 msg_type）。"""
    title, template, lines, action_label = _card_content(event_id, payload)
    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "\n".join(lines),
            },
        }
    ]
    open_url = notify_open_url()
    if open_url:
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": action_label},
                        "type": "primary",
                        "url": open_url,
                    }
                ],
            }
        )
    else:
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "请在桌面打开 zak 客户端查看详情",
                    }
                ],
            }
        )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": elements,
    }


def _card_content(
    event_id: str,
    payload: dict[str, Any],
) -> tuple[str, str, list[str], str]:
    if event_id == NOTIFY_EVENT_MANUAL_TEST:
        return "zak · 测试", "blue", ["飞书 Webhook 配置正常", "可正常接收卡片消息"], "打开 zak"

    if event_id == NOTIFY_EVENT_SCREENER_INTRADAY_DONE:
        return _screener_card("盘中选股完成", payload, "blue", "查看选股 Hub")

    if event_id == NOTIFY_EVENT_SCREENER_POST_CLOSE_DONE:
        return _screener_card("盘后选股完成", payload, "blue", "查看选股 Hub")

    if event_id == NOTIFY_EVENT_SCHEDULER_JOB_FAILED:
        job_name = str(payload.get("job_name") or payload.get("job_id") or "未知任务")
        message = str(payload.get("message") or "").strip()
        lines = [f"**任务** {job_name}"]
        if message:
            lines.append(message)
        return "定时任务失败", "red", lines, "打开 zak"

    if event_id == NOTIFY_EVENT_EMOTION_STAGE_CHANGE:
        stage_label = str(payload.get("stage_label") or payload.get("stage") or "")
        lines = [f"**阶段** {stage_label}"]
        limit_up = payload.get("limit_up_count")
        limit_down = payload.get("limit_down_count")
        if limit_up is not None and limit_down is not None:
            lines.append(f"涨停 {limit_up} · 跌停 {limit_down}")
        pos_max = payload.get("position_pct_max")
        if pos_max is not None:
            lines.append(f"建议总仓位 ≤ {int(float(pos_max) * 100)}%")
        if not payload.get("allow_new_positions", True):
            lines.append("建议：不开新仓（规则参考，非投资建议）")
        return "情绪阶段变更", "orange", lines, "打开市场页"

    if event_id == NOTIFY_EVENT_RISK_GATE_CHANGE:
        state_label = str(payload.get("state_label") or payload.get("state") or "")
        lines = [f"**状态** {state_label}"]
        for warning in payload.get("warnings") or ():
            lines.append(str(warning))
        daily = payload.get("daily_pnl_pct")
        if daily is not None:
            lines.append(f"当日盈亏合计 {float(daily):.1f}%")
        lines.append("请复盘后再操作")
        return "风控状态变更", "red", lines, "打开自选持仓"

    if event_id == NOTIFY_EVENT_POSITION_ALERT:
        name = str(payload.get("name") or "")
        symbol = str(payload.get("symbol") or "")
        lines = [f"**{name}** `{symbol}`".strip()]
        reasons = str(payload.get("reasons") or "")
        if reasons:
            lines.append(f"标签：{reasons}")
        pnl = payload.get("pnl_pct")
        if pnl is not None:
            lines.append(f"浮盈 {float(pnl):+.1f}%")
        exit_signal = str(payload.get("exit_signal") or "")
        if exit_signal:
            lines.append(f"退出信号：{exit_signal}")
        t1_locked = payload.get("t1_locked")
        if t1_locked is not None:
            lines.append(f"T+1：{'锁定' if t1_locked else '可卖'}")
        return "持仓异动", "yellow", lines, "打开自选"

    if event_id == NOTIFY_EVENT_RADAR_LEADER_READY:
        condition = str(payload.get("condition") or "雷达龙头")
        hit_count = payload.get("hit_count")
        top_name = str(payload.get("top_name") or "")
        top_symbol = str(payload.get("top_symbol") or "")
        top_score = payload.get("top_score")
        tier_label = str(payload.get("top_tier_label") or "")
        sector = str(payload.get("sector_name") or "")
        lines = [f"**{condition}**"]
        if hit_count is not None:
            lines.append(f"**命中** {hit_count} 条")
        leader = " · ".join(part for part in (top_name, top_symbol, tier_label) if part)
        if leader:
            lines.append(f"**龙一** {leader}")
        if top_score is not None:
            lines.append(f"评分 {float(top_score):.0f}")
        if sector:
            lines.append(f"主线 {sector}")
        lines.append("打开选股 Hub 查看龙头列表")
        return "龙头池更新", "green", lines, "查看选股 Hub"

    fallback = format_notify_text(event_id, payload).replace("【zak】", "").strip()
    return "zak 提醒", "blue", [fallback], "打开 zak"


def _screener_card(
    title: str,
    payload: dict[str, Any],
    template: str,
    action_label: str,
) -> tuple[str, str, list[str], str]:
    recipe = str(payload.get("recipe") or "").strip()
    hit_count = payload.get("hit_count")
    message = str(payload.get("message") or "").strip()
    lines: list[str] = []
    if recipe:
        lines.append(f"**配方** {recipe}")
    if hit_count is not None:
        lines.append(f"**命中** {hit_count} 条")
    if message:
        lines.append(message)
    lines.append("打开客户端查看选股 Hub 运行历史")
    return title, template, lines, action_label
