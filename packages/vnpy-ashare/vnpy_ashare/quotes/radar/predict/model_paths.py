"""雷达预测模型 artifact 路径。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vnpy_common.paths import VNTRADER_DIR

MODEL_DIR = VNTRADER_DIR / "models" / "radar"
MODEL_FILE = MODEL_DIR / "radar_ranker.lgb"
MANIFEST_FILE = MODEL_DIR / "radar_ranker_manifest.json"


def ensure_model_dir() -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR


def model_artifact_exists() -> bool:
    return MODEL_FILE.is_file() and MANIFEST_FILE.is_file()


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
    from datetime import datetime

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


def should_retrain_predict_model(*, max_age_days: int = 30) -> bool:
    if not lightgbm_available():
        return False
    if not model_artifact_exists():
        return True
    age = manifest_model_age_days()
    if age is None:
        return True
    return age >= max(1, int(max_age_days))


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
    return " · ".join(parts)


def lightgbm_unavailable_reason() -> str | None:
    """None 表示可用；否则为 missing_package 或 libomp。"""
    try:
        import lightgbm  # noqa: F401

        return None
    except ImportError:
        return "missing_package"
    except OSError:
        return "libomp"


def lightgbm_available() -> bool:
    return lightgbm_unavailable_reason() is None


def lightgbm_unavailable_hint() -> str:
    reason = lightgbm_unavailable_reason()
    if reason == "libomp":
        return (
            "lightgbm 已安装但无法加载 OpenMP；macOS arm64 需 "
            "/opt/homebrew/bin/brew install libomp（与 /usr/local 的 x86_64 libomp 不通用）。"
            "可执行 bash bin/ensure_libomp.sh 查看诊断。"
        )
    return "请执行 uv sync（默认含 vnpy-ashare[full]）或 uv sync --extra predict 安装 lightgbm。"
