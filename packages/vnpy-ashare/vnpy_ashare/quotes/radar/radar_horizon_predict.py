"""雷达页：未来·预测 loader（LightGBM 优先，无模型时回退统计基线）。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.predict.baseline_ranker import PREDICT_HORIZON_DAYS
from vnpy_ashare.quotes.radar.predict.model_paths import manifest_model_caption
from vnpy_ashare.quotes.radar.predict.predict_cache import get_latest_predict_cache, put_predict_cache
from vnpy_ashare.quotes.radar.predict.predict_prefs import load_predict_model_mode
from vnpy_ashare.quotes.radar.predict.predict_scan import (
    PredictScanResult,
    build_predict_subtitle,
    predict_empty_message,
    scan_predict,
)
from vnpy_ashare.quotes.radar.predict.ranker_lgb import lgb_model_ready
from vnpy_ashare.quotes.radar.radar_ai_cache import resolve_ai_hint, rows_fingerprint
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_horizon_scan import collect_daily_k_ready_vt_symbols
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, enrich_radar_rows


def _default_model_hint() -> str:
    if lgb_model_ready():
        return "LightGBM 模型 · 模型估计非保证收益"
    return "统计基线 · 无 LGB 模型时自动回退 · 模型估计非保证收益"


def build_predict_digest(rows: tuple[RadarRow, ...]) -> str:
    if not rows:
        return ""
    values = [float(row.metric_value.rstrip("%")) for row in rows if str(row.metric_value).endswith("%")]
    avg_p = sum(values) / len(values) if values else 0.0
    return f"摘要：预测 {len(rows)} 只 · 平均看涨概率 {avg_p:.0f}%"


def _empty_predict_card(
    spec: RadarCardSpec,
    *,
    subtitle: str,
    empty_message: str,
    scanned_total: int = 0,
) -> RadarCardData:
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=(),
        empty_message=empty_message,
        updated_at="",
        total_count=scanned_total,
        ai_hint=_default_model_hint(),
    )


def _card_from_scan(spec: RadarCardSpec, scan: PredictScanResult) -> RadarCardData:
    caption = manifest_model_caption() if scan.variant == "predict_lgb" else ""
    subtitle = build_predict_subtitle(
        horizon_days=PREDICT_HORIZON_DAYS,
        model_label=scan.model_label,
        scanned_total=scan.stats.scanned_total,
        top_count=len(scan.rows),
        model_caption=caption,
    )
    rows = enrich_radar_rows(scan.rows)
    if not rows:
        return _empty_predict_card(
            spec,
            subtitle=subtitle,
            empty_message=predict_empty_message(scan.stats, card_title=spec.title),
            scanned_total=scan.stats.scanned_total,
        )
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=rows,
        empty_message="",
        updated_at=scan.computed_at,
        total_count=len(rows),
        ai_hint=resolve_ai_hint(
            spec.id,
            variant="",
            fingerprint=rows_fingerprint(rows),
            digest=build_predict_digest(rows),
        )
        or _default_model_hint(),
    )


def load_outlook_predict(spec: RadarCardSpec, *, force_recompute: bool = False) -> RadarCardData:
    mode = load_predict_model_mode()
    idle_label = {
        "auto": "LightGBM" if lgb_model_ready() else "统计基线",
        "baseline": "统计基线",
        "lgb": "LightGBM",
    }.get(mode, "统计基线")
    idle_subtitle = f"约 {PREDICT_HORIZON_DAYS} 日 · {idle_label} · 模型估计非保证收益"
    caption = manifest_model_caption()
    if caption and mode in ("auto", "lgb") and lgb_model_ready():
        idle_subtitle = f"{idle_subtitle} · {caption}"

    if not force_recompute:
        cached = get_latest_predict_cache()
        if cached is not None:
            scan = PredictScanResult(
                variant=cached.variant,
                rows=cached.rows,
                stats=cached.stats,
                model_label=cached.model_label,
                computed_at=cached.computed_at,
            )
            return _card_from_scan(spec, scan)

        if not collect_daily_k_ready_vt_symbols():
            return _empty_predict_card(
                spec,
                subtitle=idle_subtitle,
                empty_message="本地暂无日 K 数据，请先运行「全市场日 K」后再刷新预测卡。",
            )
        return _empty_predict_card(
            spec,
            subtitle=idle_subtitle,
            empty_message="暂无预测快照，请点击卡片刷新；或于「工具 → 雷达模型训练」训练模型，并在定时任务中运行「雷达展望扫描」。",
        )

    scan = scan_predict(top_n=spec.top_n)
    put_predict_cache(
        variant=scan.variant,
        rows=scan.rows,
        stats=scan.stats,
        model_label=scan.model_label,
        computed_at=scan.computed_at,
    )
    return _card_from_scan(spec, scan)


def build_predict_ai_prompt(data: RadarCardData) -> str:
    model_note = "LightGBM 截面模型" if "LightGBM" in (data.subtitle or "") else "统计基线排序"
    lines = [
        "请解读雷达「未来·预测」：",
        f"1. 说明本卡当前为{model_note}，看涨概率为模型估计",
        "2. 非确定性预测，禁止给出买卖建议",
        "3. 概括 Top 标的共性并标注相对强弱",
        "4. 不要编造未出现在数据中的价格或指标",
        "",
        data.subtitle,
        "",
    ]
    if not data.rows:
        lines.append(data.empty_message or "（暂无数据）")
        return "\n".join(lines).strip()
    for row in data.rows:
        price = f"{row.price:.2f}" if row.price is not None else "—"
        change = f"{row.change_pct:+.2f}%" if row.change_pct is not None else "—"
        lines.append(
            f"- {row.name}({row.symbol}) {change} 现价{price} · {row.metric_label} {row.metric_value} · {row.sub_label} {row.sub_value}"
        )
    return "\n".join(lines).strip()
