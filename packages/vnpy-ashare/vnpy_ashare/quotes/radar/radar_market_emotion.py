"""盘面·环境 loader（情绪周期摘要）。"""

from __future__ import annotations

from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.market.emotion_cycle import format_mode_label, load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow

_STAT_ROW_PREFIX = "__stat__:"


def _stat_row(
    row_id: str,
    *,
    name: str,
    metric_label: str,
    metric_value: str,
    sub_label: str = "",
    sub_value: str = "",
) -> RadarRow:
    return RadarRow(
        vt_symbol=f"{_STAT_ROW_PREFIX}{row_id}",
        name=name,
        symbol="",
        price=None,
        change_pct=None,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def is_stat_row(vt_symbol: str) -> bool:
    return str(vt_symbol or "").startswith(_STAT_ROW_PREFIX)


def load_market_emotion(spec: RadarCardSpec) -> RadarCardData:
    snapshot = load_emotion_cycle_snapshot(fetch_if_missing=True)
    if snapshot is None:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="等待市场广度数据",
            rows=(),
            empty_message="暂无情绪数据，请先采集行情或打开「市场」页。",
            updated_at=format_china_datetime_minute(),
        )

    inputs = snapshot.inputs
    pos_max = int(snapshot.position_pct_max * 100)
    pos_min = int(snapshot.position_pct_min * 100)
    if pos_max <= 0:
        pos_text = "建议空仓"
    elif pos_min == pos_max:
        pos_text = f"建议 {pos_max}%"
    else:
        pos_text = f"建议 {pos_min}–{pos_max}%"

    modes = "、".join(format_mode_label(mode) for mode in snapshot.allowed_modes) if snapshot.allowed_modes else "无"
    allow_text = "可新开" if snapshot.allow_new_positions else "不宜新开"
    subtitle = (
        f"{snapshot.stage_label} · {pos_text} · 系数 {snapshot.position_factor:.2f} · {allow_text} · "
        f"涨停 {inputs.get('limit_up_count', '—')} / 跌停 {inputs.get('limit_down_count', '—')}"
    )

    rows = [
        _stat_row("stage", name="情绪阶段", metric_label="阶段", metric_value=snapshot.stage_label, sub_label="仓位", sub_value=pos_text),
        _stat_row(
            "breadth",
            name="涨跌停",
            metric_label="涨停",
            metric_value=str(inputs.get("limit_up_count", "—")),
            sub_label="跌停",
            sub_value=str(inputs.get("limit_down_count", "—")),
        ),
        _stat_row(
            "ladder",
            name="连板梯队",
            metric_label="最高板",
            metric_value=str(inputs.get("max_limit_times", "—")),
            sub_label="梯队层",
            sub_value=str(inputs.get("limit_ladder_depth", "—")),
        ),
        _stat_row(
            "modes",
            name="允许模式",
            metric_label="模式",
            metric_value=modes[:12],
            sub_label="上涨占比",
            sub_value=f"{float(inputs.get('up_ratio', 0)) * 100:.0f}%" if inputs.get("up_ratio") is not None else "—",
        ),
    ]
    if snapshot.warnings:
        rows.append(
            _stat_row(
                "warn",
                name="风险提示",
                metric_label="提示",
                metric_value=str(snapshot.warnings[0])[:16],
                sub_label="更多" if len(snapshot.warnings) > 1 else "",
                sub_value=str(snapshot.warnings[1])[:16] if len(snapshot.warnings) > 1 else "",
            )
        )

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at=snapshot.updated_at or format_china_datetime_minute(),
        total_count=len(rows),
    )
