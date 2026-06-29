"""自选信号缓存 payload 序列化。"""

from __future__ import annotations

import json
from typing import Any

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot, signal_snapshot_to_dict


def snapshot_to_payload(snapshot: SignalSnapshot) -> str:
    data = signal_snapshot_to_dict(snapshot)
    data["reasons"] = list(snapshot.reasons)
    data["warnings"] = list(snapshot.warnings)
    return json.dumps(data, ensure_ascii=False)


def snapshot_from_payload(text: str) -> SignalSnapshot:
    data: dict[str, Any] = json.loads(text)
    return SignalSnapshot(
        vt_symbol=str(data.get("vt_symbol") or ""),
        strategy_id=str(data.get("strategy_id") or ""),
        as_of=str(data.get("as_of") or ""),
        signal=data.get("signal") or "na",
        signal_label=str(data.get("signal_label") or "—"),
        signal_date=data.get("signal_date"),
        ref_buy_price=data.get("ref_buy_price"),
        ref_sell_price=data.get("ref_sell_price"),
        strength=data.get("strength"),
        reason_summary=str(data.get("reason_summary") or ""),
        reasons=tuple(data.get("reasons") or ()),
        warnings=tuple(data.get("warnings") or ()),
        last_close=data.get("last_close"),
        action_ref_buy_price=data.get("action_ref_buy_price"),
        action_ref_sell_price=data.get("action_ref_sell_price"),
        fast_ma=data.get("fast_ma"),
        slow_ma=data.get("slow_ma"),
        volume_ratio_5d=data.get("volume_ratio_5d"),
        ma_gap_pct=data.get("ma_gap_pct"),
        strength_cross=data.get("strength_cross"),
        strength_alignment=data.get("strength_alignment"),
        strength_volume=data.get("strength_volume"),
        strength_pattern=data.get("strength_pattern"),
        relative_index_pct=data.get("relative_index_pct"),
    )
