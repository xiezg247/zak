"""买点模式评估：打板 / 半路 / 低吸（A-06）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.board import matches_board
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot, format_mode_label, load_emotion_cycle_snapshot
from vnpy_ashare.quotes.radar.radar_models import merge_row_quotes, quotes_for_vt_symbols
from vnpy_ashare.screener.hard_filters import is_at_limit_board

EntryMode = Literal["limit_board", "halfway", "pullback"]

_MODE_LABELS: dict[EntryMode, str] = {
    "limit_board": "打板",
    "halfway": "半路",
    "pullback": "低吸",
}


@dataclass(frozen=True)
class EntryModeScore:
    mode: EntryMode
    label: str
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EntryModeEvaluation:
    vt_symbol: str
    name: str
    symbol: str
    board_tag: str
    change_pct: float | None
    at_limit_board: bool
    leader_tier: str
    limit_times: float | None
    recommended_mode: EntryMode | None
    recommended_label: str
    scores: tuple[EntryModeScore, ...]
    emotion_stage: str
    emotion_stage_label: str
    allow_new_positions: bool
    allowed_modes: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "vt_symbol": self.vt_symbol,
            "name": self.name,
            "symbol": self.symbol,
            "board_tag": self.board_tag,
            "change_pct": self.change_pct,
            "at_limit_board": self.at_limit_board,
            "leader_tier": self.leader_tier,
            "limit_times": self.limit_times,
            "recommended_mode": self.recommended_mode,
            "recommended_label": self.recommended_label,
            "scores": [
                {
                    "mode": item.mode,
                    "label": item.label,
                    "score": round(item.score, 1),
                    "reasons": list(item.reasons),
                }
                for item in self.scores
            ],
            "emotion_stage": self.emotion_stage,
            "emotion_stage_label": self.emotion_stage_label,
            "allow_new_positions": self.allow_new_positions,
            "allowed_modes": list(self.allowed_modes),
            "allowed_mode_labels": [format_mode_label(mode) for mode in self.allowed_modes],
            "warnings": list(self.warnings),
        }


def _board_tag(symbol: str) -> str:
    if matches_board(symbol, "创业板") or matches_board(symbol, "科创板"):
        return "20cm"
    return "10cm"


def _score_mode(
    mode: EntryMode,
    *,
    base: float,
    reasons: list[str],
    allowed: bool,
) -> EntryModeScore:
    score = base
    if not allowed:
        score = min(score, 25.0)
        reasons = [*reasons, "当前情绪阶段未开放该模式"]
    return EntryModeScore(mode=mode, label=_MODE_LABELS[mode], score=round(score, 1), reasons=tuple(reasons))


def evaluate_entry_mode(
    row: dict[str, Any],
    *,
    cycle: EmotionCycleSnapshot | None = None,
    leader_tier: str = "",
    limit_times: float | None = None,
) -> EntryModeEvaluation | None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    symbol = str(row.get("symbol") or vt_symbol.split(".")[0]).strip()
    if not vt_symbol and not symbol:
        return None
    if not vt_symbol:
        exchange = str(row.get("exchange") or "SSE")
        vt_symbol = f"{symbol}.{exchange}"

    snapshot = cycle if cycle is not None else load_emotion_cycle_snapshot(fetch_if_missing=True)
    name = str(row.get("name") or symbol)
    change_raw = row.get("change_pct", row.get("pct_chg"))
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    board = _board_tag(symbol)
    at_limit = is_at_limit_board(row)
    tier = str(leader_tier or row.get("leader_tier") or "").strip()
    boards_raw = limit_times if limit_times is not None else row.get("limit_times")
    boards = float(boards_raw) if isinstance(boards_raw, (int, float)) else None

    allowed_env = set(snapshot.allowed_modes) if snapshot is not None else set()
    stage = snapshot.stage if snapshot is not None else "divergence"
    stage_label = snapshot.stage_label if snapshot is not None else "分歧"
    allow_new = snapshot.allow_new_positions if snapshot is not None else True
    warnings: list[str] = list(snapshot.warnings) if snapshot is not None else []

    if not allow_new:
        warnings.append("情绪阶段不建议短线新开仓")

    limit_reasons: list[str] = []
    halfway_reasons: list[str] = []
    pullback_reasons: list[str] = []

    limit_score = 20.0
    halfway_score = 20.0
    pullback_score = 20.0

    if board == "20cm":
        limit_score = 10.0
        limit_reasons.append("创/科 20cm 不建议打板")
        if change_pct is not None and 7.0 <= change_pct < 19.5:
            halfway_score += 35.0
            halfway_reasons.append(f"涨幅 {change_pct:+.2f}% 适合半路")
        if change_pct is not None and change_pct < 7.0:
            pullback_score += 30.0
            pullback_reasons.append("涨幅未充分，更宜等承接")
    else:
        if at_limit:
            limit_score += 45.0
            limit_reasons.append("已触及涨跌停附近")
        elif change_pct is not None and change_pct >= 9.0:
            limit_score += 30.0
            limit_reasons.append(f"涨幅 {change_pct:+.2f}% 接近涨停")
        if change_pct is not None and 3.0 <= change_pct < 9.8 and not at_limit:
            halfway_score += 40.0
            halfway_reasons.append(f"涨幅 {change_pct:+.2f}% 处于半路区间")
        if tier in {"dragon_1", "dragon_2"}:
            limit_score += 15.0
            limit_reasons.append(f"板块{'龙一' if tier == 'dragon_1' else '龙二'}")
        if boards is not None and boards >= 1:
            limit_score += 10.0
            limit_reasons.append(f"连板 {int(boards)}")

    if stage == "divergence":
        pullback_score += 25.0
        pullback_reasons.append("分歧期优先核心低吸")
    if stage in {"startup", "climax"}:
        limit_score += 10.0
        halfway_score += 10.0
        limit_reasons.append(f"环境 {stage_label}")
        halfway_reasons.append(f"环境 {stage_label}")

    if change_pct is not None and -5.0 <= change_pct <= 1.0:
        pullback_score += 20.0
        pullback_reasons.append("日内回调/横盘，观察承接")

    scores = (
        _score_mode("limit_board", base=limit_score, reasons=limit_reasons, allowed="limit_board" in allowed_env),
        _score_mode("halfway", base=halfway_score, reasons=halfway_reasons, allowed="halfway" in allowed_env),
        _score_mode("pullback", base=pullback_score, reasons=pullback_reasons, allowed="pullback" in allowed_env),
    )
    ranked = tuple(sorted(scores, key=lambda item: (-item.score, item.mode)))
    recommended: EntryMode | None = None
    if allow_new and ranked[0].score >= 40.0:
        recommended = ranked[0].mode
    elif not allow_new:
        recommended = None

    return EntryModeEvaluation(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        board_tag=board,
        change_pct=change_pct,
        at_limit_board=at_limit,
        leader_tier=tier,
        limit_times=boards,
        recommended_mode=recommended,
        recommended_label=_MODE_LABELS[recommended] if recommended else "观望",
        scores=ranked,
        emotion_stage=stage,
        emotion_stage_label=stage_label,
        allow_new_positions=allow_new,
        allowed_modes=tuple(allowed_env),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def evaluate_entry_mode_for_symbol(symbol: str) -> dict[str, Any]:

    item = parse_stock_symbol(symbol)
    if item is None:
        return {"error": f"无法解析代码: {symbol}"}

    quotes = quotes_for_vt_symbols([item.vt_symbol])
    row = merge_row_quotes(quotes.get(item.vt_symbol, {"vt_symbol": item.vt_symbol, "symbol": item.symbol}))
    result = evaluate_entry_mode(row)
    if result is None:
        return {"error": f"无法评估: {symbol}"}
    return result.to_dict()
