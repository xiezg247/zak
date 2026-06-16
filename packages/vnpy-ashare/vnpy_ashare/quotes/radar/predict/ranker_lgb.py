"""雷达预测 LightGBM 排序模型（可选依赖）。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from vnpy_ashare.quotes.radar.predict.factor_panel import FEATURE_NAMES, feature_vector, features_from_quote_row
from vnpy_ashare.quotes.radar.predict.model_paths import MODEL_FILE, lightgbm_available, load_manifest, model_artifact_exists
from vnpy_ashare.quotes.radar.predict.types import PredictHit


def lgb_model_ready() -> bool:
    return lightgbm_available() and model_artifact_exists()


@lru_cache(maxsize=1)
def _load_booster():
    import lightgbm as lgb

    if not MODEL_FILE.is_file():
        msg = f"模型文件不存在：{MODEL_FILE}"
        raise FileNotFoundError(msg)
    return lgb.Booster(model_file=str(MODEL_FILE))


def _median_fill(features: dict[str, float], manifest: dict[str, Any]) -> dict[str, float]:
    medians = manifest.get("feature_medians") or {}
    merged = dict(features)
    for name in FEATURE_NAMES:
        if name not in merged or merged[name] == 0.0:
            median = medians.get(name)
            if isinstance(median, (int, float)):
                merged[name] = float(median)
    return merged


def rank_lgb_predict(rows: list[dict[str, Any]]) -> list[PredictHit]:
    """对候选行情行做 LGB 推理，返回按模型分降序的命中。"""
    if not rows:
        return []
    if not lgb_model_ready():
        return []

    manifest = load_manifest() or {}
    feature_names = tuple(manifest.get("feature_names") or FEATURE_NAMES)
    booster = _load_booster()

    hits: list[PredictHit] = []
    for row in rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            continue
        merged_features = row.get("predict_features")
        if isinstance(merged_features, dict):
            features = _median_fill({str(k): float(v) for k, v in merged_features.items()}, manifest)
        else:
            features = _median_fill(features_from_quote_row(row), manifest)
        vector = feature_vector(features, feature_names=feature_names)
        prob = float(booster.predict([vector])[0])
        prob = max(0.05, min(0.95, prob))
        score = round(prob * 100.0, 1)
        hits.append(
            PredictHit(
                vt_symbol=vt_symbol,
                score=score,
                p_up=round(prob, 3),
                score_label="模型分",
                model_label=str(manifest.get("model_label") or "LightGBM"),
            )
        )
    hits.sort(key=lambda item: (-item.score, -item.p_up, item.vt_symbol))
    return hits


def clear_booster_cache() -> None:
    _load_booster.cache_clear()
