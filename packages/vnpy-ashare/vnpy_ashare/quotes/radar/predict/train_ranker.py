"""雷达预测 LightGBM 训练（CLI / 定时任务入口）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median

from vnpy_ashare.data.bar_access import iter_bar_overviews, load_scope_bars
from vnpy_ashare.domain.datetime import format_china_datetime_minute
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.quotes.radar.predict.factor_panel import FEATURE_NAMES, features_from_bar_window
from vnpy_ashare.quotes.radar.predict.labels import forward_direction_label, forward_return_pct
from vnpy_ashare.quotes.radar.predict.model_paths import MODEL_FILE, ensure_model_dir, lightgbm_available, lightgbm_unavailable_hint, save_manifest
from vnpy_ashare.quotes.radar.predict.ranker_lgb import clear_booster_cache


@dataclass(frozen=True)
class TrainRankerResult:
    success: bool
    message: str
    sample_count: int = 0
    val_auc: float | None = None


def _collect_symbol_items(*, max_symbols: int, min_bars: int) -> list[StockItem]:
    items: list[StockItem] = []
    for row in iter_bar_overviews(scope="daily"):
        if int(row.count or 0) < min_bars:
            continue
        items.append(StockItem(symbol=row.symbol, exchange=row.exchange))
        if len(items) >= max_symbols:
            break
    return items


def build_training_samples(
    items: list[StockItem],
    *,
    horizon: int = 5,
    sample_stride: int = 3,
    min_history: int = 30,
) -> tuple[list[list[float]], list[int], list[float]]:
    features_rows: list[list[float]] = []
    labels: list[int] = []
    returns: list[float] = []

    for item in items:
        bars = load_scope_bars(
            item.symbol,
            item.exchange,
            "daily",
            datetime(1990, 1, 1),
            datetime.now(),
        )
        if len(bars) < min_history + horizon + 5:
            continue
        closes = [float(bar.close_price) for bar in bars]
        volumes = [float(bar.volume) for bar in bars]
        last_index = len(closes) - horizon - 1
        for index in range(min_history, last_index + 1, max(1, sample_stride)):
            feature_map = features_from_bar_window(closes, volumes, end_index=index)
            label = forward_direction_label(closes, index=index, horizon=horizon)
            ret = forward_return_pct(closes, index=index, horizon=horizon)
            if feature_map is None or label is None or ret is None:
                continue
            features_rows.append([float(feature_map[name]) for name in FEATURE_NAMES])
            labels.append(label)
            returns.append(ret)
    return features_rows, labels, returns


def _split_train_valid(
    features_rows: list[list[float]],
    labels: list[int],
    *,
    valid_ratio: float = 0.2,
) -> tuple[list[list[float]], list[int], list[list[float]], list[int]]:
    if not features_rows:
        return [], [], [], []
    split = max(1, int(len(features_rows) * (1.0 - valid_ratio)))
    x_train = features_rows[:split]
    y_train = labels[:split]
    x_valid = features_rows[split:]
    y_valid = labels[split:]
    return x_train, y_train, x_valid, y_valid


def run_train_radar_ranker(
    *,
    horizon: int = 5,
    max_symbols: int = 400,
    min_bars: int = 80,
    sample_stride: int = 3,
) -> TrainRankerResult:
    if not lightgbm_available():
        return TrainRankerResult(
            success=False,
            message=lightgbm_unavailable_hint(),
        )

    items = _collect_symbol_items(max_symbols=max(50, int(max_symbols)), min_bars=min_bars)
    if len(items) < 20:
        return TrainRankerResult(success=False, message="本地日 K 样本不足，请先同步全市场日 K。")

    features_rows, labels, _returns = build_training_samples(
        items,
        horizon=horizon,
        sample_stride=sample_stride,
        min_history=30,
    )
    if len(features_rows) < 200:
        return TrainRankerResult(
            success=False,
            message=f"有效训练样本过少（{len(features_rows)}），请增大 max_symbols 或补全 K 线。",
            sample_count=len(features_rows),
        )

    import lightgbm as lgb
    import numpy as np

    x_train, y_train, x_valid, y_valid = _split_train_valid(features_rows, labels)
    train_set = lgb.Dataset(np.asarray(x_train), label=np.asarray(y_train), feature_name=list(FEATURE_NAMES))
    valid_set = lgb.Dataset(np.asarray(x_valid), label=np.asarray(y_valid), feature_name=list(FEATURE_NAMES))

    params = {
        "objective": "binary",
        "metric": "auc",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "verbose": -1,
    }
    booster = lgb.train(
        params,
        train_set,
        num_boost_round=120,
        valid_sets=[valid_set],
        valid_names=["valid"],
    )

    ensure_model_dir()
    booster.save_model(str(MODEL_FILE))

    val_auc: float | None = None
    best = getattr(booster, "best_score", None) or {}
    valid_scores = best.get("valid") if isinstance(best, dict) else None
    if isinstance(valid_scores, dict) and "auc" in valid_scores:
        val_auc = round(float(valid_scores["auc"]), 4)

    medians: dict[str, float] = {}
    for col_index, name in enumerate(FEATURE_NAMES):
        column = [row[col_index] for row in features_rows]
        medians[name] = round(float(median(column)), 4)

    save_manifest(
        {
            "model_label": "LightGBM",
            "feature_names": list(FEATURE_NAMES),
            "feature_medians": medians,
            "horizon_days": horizon,
            "sample_count": len(features_rows),
            "symbol_count": len(items),
            "val_auc": val_auc,
            "trained_at": format_china_datetime_minute(),
        }
    )
    clear_booster_cache()

    auc_text = f"{val_auc:.3f}" if val_auc is not None else "—"
    return TrainRankerResult(
        success=True,
        message=f"训练完成：样本 {len(features_rows)} · 标的 {len(items)} · 验证 AUC {auc_text} · 已写入 {MODEL_FILE}",
        sample_count=len(features_rows),
        val_auc=val_auc,
    )
