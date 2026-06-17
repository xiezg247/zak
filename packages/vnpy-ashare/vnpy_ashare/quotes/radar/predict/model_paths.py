"""雷达预测模型 artifact 路径（预留后续 ML 训练接入）。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from vnpy_common.paths import VNTRADER_DIR

MODEL_DIR = VNTRADER_DIR / "models" / "radar"
MANIFEST_FILE = MODEL_DIR / "radar_ranker_manifest.json"


def ensure_model_dir() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR


def load_manifest() -> dict[str, Any] | None:
    if not MANIFEST_FILE.is_file():
        return None
    try:
        payload = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def save_manifest(payload: dict[str, Any]) -> None:
    ensure_model_dir()
    MANIFEST_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def manifest_model_age_days(manifest: dict[str, Any] | None = None) -> int | None:
    payload = manifest if manifest is not None else load_manifest()
    if not payload:
        return None
    trained_at = str(payload.get("trained_at") or "").strip()
    if not trained_at:
        return None
    try:
        trained = datetime.strptime(trained_at, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    delta = datetime.now() - trained
    return max(0, int(delta.total_seconds() // 86400))


def manifest_model_caption(manifest: dict[str, Any] | None = None) -> str:
    payload = manifest if manifest is not None else load_manifest()
    if not payload:
        return ""
    parts: list[str] = []
    trained_at = str(payload.get("trained_at") or "").strip()
    if trained_at:
        parts.append(f"训练 {trained_at}")
    val_auc = payload.get("val_auc")
    if isinstance(val_auc, (int, float)):
        parts.append(f"验证 AUC {float(val_auc):.3f}")
    sample_count = payload.get("sample_count")
    if isinstance(sample_count, int) and sample_count > 0:
        parts.append(f"样本 {sample_count}")
    model_label = str(payload.get("model_label") or "").strip()
    if model_label:
        parts.append(model_label)
    return " · ".join(parts)
