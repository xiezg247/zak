"""情绪周期 subtitle 后缀（雷达卡片）。"""

from __future__ import annotations

from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot, load_emotion_cycle_snapshot, peek_emotion_cycle_snapshot


def _resolve_snapshot(*, snapshot: EmotionCycleSnapshot | None) -> EmotionCycleSnapshot | None:
    if snapshot is not None:
        return snapshot
    peeked = peek_emotion_cycle_snapshot()
    if peeked is not None:
        return peeked
    return load_emotion_cycle_snapshot(fetch_if_missing=False)


def emotion_cycle_subtitle_suffix(*, snapshot: EmotionCycleSnapshot | None = None) -> str:
    cycle = _resolve_snapshot(snapshot=snapshot)
    if cycle is None:
        return ""
    pos_max = int(cycle.position_pct_max * 100)
    if pos_max <= 0:
        pos_text = "建议空仓"
    else:
        pos_min = int(cycle.position_pct_min * 100)
        pos_text = f"建议 {pos_min}–{pos_max}%" if pos_min != pos_max else f"建议 {pos_max}%"
    return f" · 环境：{cycle.stage_label} · {pos_text}"


def append_emotion_cycle_to_subtitle(subtitle: str, *, snapshot: EmotionCycleSnapshot | None = None) -> str:
    suffix = emotion_cycle_subtitle_suffix(snapshot=snapshot)
    if not suffix:
        return subtitle
    if "环境：" in subtitle:
        return subtitle
    return f"{subtitle}{suffix}" if subtitle else suffix.lstrip(" ·")
