"""板块未来 N 日资金展望：LLM 情景口径（C）。"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from vnpy_ashare.domain.market.sector_flow import (
    LLM_OUTLOOK_DISCLAIMER,
    OUTLOOK_HORIZON_DAYS,
    SectorFlowOutlookBundle,
    SectorFlowOutlookCompareRow,
    SectorFlowOutlookDay,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRow,
)
from vnpy_ashare.services.sector_flow_outlook_strategy import resolve_strategy_signal_config
from vnpy_ashare.storage.cache.sector_flow_outlook_llm_cache import (
    get_outlook_llm_cache,
    put_outlook_llm_cache,
)

_LLM_TOP_N = 16
_VALID_BIASES = frozenset({"偏多", "偏空", "震荡"})


def _sector_lookup(bundle: SectorFlowOutlookBundle) -> dict[str, SectorFlowRow]:
    lookup: dict[str, SectorFlowRow] = {}
    for row in bundle.continuation.rows:
        lookup[row.sector.sector_id] = row.sector
    for row in bundle.strategy.rows:
        lookup[row.sector.sector_id] = row.sector
    for compare in bundle.compare_rows:
        lookup[compare.sector.sector_id] = compare.sector
    return lookup


def _day_summary(row: SectorFlowOutlookRow | None, forward_dates: tuple[str, ...]) -> str:
    if row is None or not row.days:
        return "—"
    parts: list[str] = []
    for index, trade_date in enumerate(forward_dates):
        if index >= len(row.days):
            break
        day = row.days[index]
        label = _format_trade_date_short(trade_date)
        parts.append(f"{label}{day.bias}{day.strength:.2f}")
    headline = row.headline_pattern or ""
    rationale = row.rationale or ""
    detail = " ".join(parts)
    if headline:
        return f"{detail} · {headline} · {rationale}"
    return detail


def _format_trade_date_short(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"T+{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned


def _select_prompt_sectors(bundle: SectorFlowOutlookBundle, *, top_n: int = _LLM_TOP_N) -> list[SectorFlowOutlookCompareRow]:
    rows = list(bundle.compare_rows)
    if rows:
        agreement_rank = {"一致": 0, "分歧": 1, "仅延续": 2, "仅策略": 3, "—": 4}

        def _rank(item: SectorFlowOutlookCompareRow) -> tuple:
            cont_strength = item.continuation.days[0].strength if item.continuation and item.continuation.days else 0.0
            strat_strength = item.strategy.days[0].strength if item.strategy and item.strategy.days else 0.0
            return (
                agreement_rank.get(item.agreement, 9),
                -(cont_strength + strat_strength),
                item.sector.name,
            )

        rows.sort(key=_rank)
        return rows[:top_n]

    merged: list[SectorFlowOutlookRow] = []
    seen: set[str] = set()
    for row in (*bundle.continuation.rows, *bundle.strategy.rows):
        if row.sector.sector_id in seen:
            continue
        seen.add(row.sector.sector_id)
        merged.append(row)
    merged.sort(
        key=lambda item: (
            -(item.days[0].strength if item.days else 0.0),
            item.sector.name,
        )
    )
    return [
        SectorFlowOutlookCompareRow(
            sector=item.sector,
            continuation=item if item.source == "continuation" else None,
            strategy=item if item.source == "strategy" else None,
            agreement="—",
        )
        for item in merged[:top_n]
    ]


def outlook_bundle_fingerprint(bundle: SectorFlowOutlookBundle, *, strategy_class: str | None = None) -> str:
    config = resolve_strategy_signal_config(strategy_class)
    strategy_key = config.cache_key()
    sectors = _select_prompt_sectors(bundle)
    parts: list[str] = [bundle.continuation.sector_kind, strategy_key]
    forward_dates = bundle.continuation.forward_dates or bundle.strategy.forward_dates
    parts.append("|".join(forward_dates))
    for item in sectors:
        cont = item.continuation
        strat = item.strategy
        cont_bias = cont.days[0].bias if cont and cont.days else ""
        strat_bias = strat.days[0].bias if strat and strat.days else ""
        cont_strength = cont.days[0].strength if cont and cont.days else 0.0
        strat_strength = strat.days[0].strength if strat and strat.days else 0.0
        parts.append(f"{item.sector.sector_id}:{cont_bias}:{cont_strength:.2f}:{strat_bias}:{strat_strength:.2f}")
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return digest[:24]


def build_llm_outlook_empty(
    bundle: SectorFlowOutlookBundle,
    *,
    hint: str = "",
) -> SectorFlowOutlookSnapshot:
    forward_dates = bundle.continuation.forward_dates or bundle.strategy.forward_dates
    return SectorFlowOutlookSnapshot(
        forward_dates=forward_dates,
        rows=(),
        sector_kind=bundle.continuation.sector_kind,
        source="llm",
        empty_hint=hint or "展望C 暂无 AI 情景，请点击「生成AI展望」",
        disclaimer=LLM_OUTLOOK_DISCLAIMER,
        data_mode=bundle.continuation.data_mode,
    )


def load_llm_outlook_from_cache(
    bundle: SectorFlowOutlookBundle,
    *,
    strategy_class: str | None = None,
) -> SectorFlowOutlookSnapshot | None:
    if not bundle.continuation.rows and not bundle.strategy.rows:
        return None
    config = resolve_strategy_signal_config(strategy_class)
    fingerprint = outlook_bundle_fingerprint(bundle, strategy_class=strategy_class)
    cached = get_outlook_llm_cache(
        sector_kind=bundle.continuation.sector_kind,
        strategy_key=config.cache_key(),
        fingerprint=fingerprint,
        sector_lookup=_sector_lookup(bundle),
    )
    return cached


def attach_llm_outlook(
    bundle: SectorFlowOutlookBundle,
    *,
    strategy_class: str | None = None,
) -> SectorFlowOutlookBundle:
    cached = load_llm_outlook_from_cache(bundle, strategy_class=strategy_class)
    if cached is not None:
        return bundle.model_copy(update={"llm": cached})
    empty = build_llm_outlook_empty(bundle)
    return bundle.model_copy(update={"llm": empty})


def build_llm_outlook_prompt(
    bundle: SectorFlowOutlookBundle,
    *,
    strategy_class: str | None = None,
    top_n: int = _LLM_TOP_N,
) -> list[dict[str, str]]:
    if not bundle.continuation.rows and not bundle.strategy.rows:
        raise ValueError("延续A与策略B均无数据，无法生成 AI 展望")
    config = resolve_strategy_signal_config(strategy_class)
    from vnpy_ashare.quotes.radar.outlook_strategy_prefs import outlook_strategy_label

    strategy_label = outlook_strategy_label(config.class_name)
    forward_dates = bundle.continuation.forward_dates or bundle.strategy.forward_dates
    kind_label = "概念" if bundle.continuation.sector_kind == "concept" else "行业"
    date_labels = " / ".join(_format_trade_date_short(item) for item in forward_dates)

    lines = [
        f"板块类型：{kind_label}",
        f"展望窗口：{date_labels}（共 {len(forward_dates)} 个交易日）",
        f"策略B口径：{strategy_label}",
        "",
        "以下为各行业延续A / 策略B 结构化摘要（仅供情景参考，非真实未来资金）：",
    ]
    for item in _select_prompt_sectors(bundle, top_n=top_n):
        cont_summary = _day_summary(item.continuation, forward_dates)
        strat_summary = _day_summary(item.strategy, forward_dates)
        agreement = item.agreement or "—"
        lines.append(f"- {item.sector.name}（id={item.sector.sector_id}，对照={agreement}）\n  A延续：{cont_summary}\n  B策略：{strat_summary}")

    user_content = "\n".join(lines)
    system_content = (
        "你是 A 股板块资金分析助手。根据用户提供的延续A（资金动量规则）与策略B（成分股信号聚合）数据，"
        f"为每个行业生成未来 {OUTLOOK_HORIZON_DAYS} 个交易日的 AI 情景展望。"
        "要求：\n"
        "1. 仅输出合法 JSON，不要 Markdown 代码块或解释文字\n"
        "2. 每个行业 days 数组长度与 forward_dates 一致，trade_date 必须原样使用用户给出的日期\n"
        "3. bias 只能是：偏多、偏空、震荡；strength 为 0~1 小数\n"
        "4. 禁止编造具体净流入金额、目标价或买卖建议\n"
        "5. headline 不超过 20 字，rationale 不超过 80 字\n"
        "JSON 格式："
        '{"sectors":[{"sector_id":"...","days":[{"trade_date":"YYYYMMDD","bias":"偏多","strength":0.65}],'
        '"headline":"...","rationale":"..."}]}'
    )
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": (f"{user_content}\n\nforward_dates={json.dumps(list(forward_dates), ensure_ascii=False)}\n请为上述全部行业输出 sectors 数组。"),
        },
    ]


def _extract_json_payload(text: str) -> Any:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("LLM 返回为空")
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise ValueError("LLM 返回不是合法 JSON") from None


def parse_llm_outlook_response(
    text: str,
    *,
    bundle: SectorFlowOutlookBundle,
    forward_dates: tuple[str, ...],
) -> tuple[SectorFlowOutlookRow, ...]:
    payload = _extract_json_payload(text)
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON 根节点必须是对象")
    sectors = payload.get("sectors")
    if not isinstance(sectors, list):
        raise ValueError("LLM JSON 缺少 sectors 数组")

    lookup = _sector_lookup(bundle)
    rows: list[SectorFlowOutlookRow] = []
    for item in sectors:
        if not isinstance(item, dict):
            continue
        sector_id = str(item.get("sector_id") or "").strip()
        sector = lookup.get(sector_id)
        if sector is None:
            name = str(item.get("sector_name") or "").strip()
            for candidate in lookup.values():
                if candidate.name == name:
                    sector = candidate
                    break
        if sector is None:
            continue
        days_payload = item.get("days")
        if not isinstance(days_payload, list):
            continue
        days: list[SectorFlowOutlookDay] = []
        for index, trade_date in enumerate(forward_dates):
            raw = None
            for candidate in days_payload:
                if isinstance(candidate, dict) and str(candidate.get("trade_date") or "").strip() == trade_date:
                    raw = candidate
                    break
            if raw is None and index < len(days_payload) and isinstance(days_payload[index], dict):
                raw = days_payload[index]
            if not isinstance(raw, dict):
                continue
            bias = str(raw.get("bias") or "").strip()
            if bias not in _VALID_BIASES:
                bias = "震荡"
            try:
                strength = float(raw.get("strength", 0.0))
            except (TypeError, ValueError):
                strength = 0.0
            days.append(
                SectorFlowOutlookDay(
                    trade_date=trade_date,
                    bias=bias,
                    strength=max(0.0, min(1.0, round(strength, 2))),
                )
            )
        if not days:
            continue
        rows.append(
            SectorFlowOutlookRow(
                sector=sector,
                days=tuple(days),
                headline_pattern=str(item.get("headline") or item.get("headline_pattern") or "").strip() or "AI情景",
                rationale=str(item.get("rationale") or "").strip() or "基于延续A与策略B的 AI 情景参考",
                source="llm",
            )
        )

    if not rows:
        raise ValueError("LLM 未返回可解析的行业展望")
    rows.sort(
        key=lambda row: (
            -(row.days[0].strength if row.days else 0.0),
            row.sector.name,
        )
    )
    return tuple(rows)


def generate_llm_outlook(
    bundle: SectorFlowOutlookBundle,
    config: Any,
    *,
    strategy_class: str | None = None,
) -> SectorFlowOutlookSnapshot:
    from vnpy_ashare.domain.time.china import format_china_datetime_minute
    from vnpy_llm.chat.client import complete_chat_completion

    messages = build_llm_outlook_prompt(bundle, strategy_class=strategy_class)
    text = complete_chat_completion(config, messages, max_tokens=2800)
    forward_dates = bundle.continuation.forward_dates or bundle.strategy.forward_dates
    rows = parse_llm_outlook_response(text, bundle=bundle, forward_dates=forward_dates)
    snapshot = SectorFlowOutlookSnapshot(
        forward_dates=forward_dates,
        rows=rows,
        sector_kind=bundle.continuation.sector_kind,
        source="llm",
        updated_at=f"AI展望·{format_china_datetime_minute()}",
        disclaimer=LLM_OUTLOOK_DISCLAIMER,
        data_mode=bundle.continuation.data_mode,
    )
    signal_config = resolve_strategy_signal_config(strategy_class)
    fingerprint = outlook_bundle_fingerprint(bundle, strategy_class=strategy_class)
    put_outlook_llm_cache(
        snapshot,
        strategy_key=signal_config.cache_key(),
        fingerprint=fingerprint,
    )
    return snapshot


def format_llm_ai_lines(
    outlook: SectorFlowOutlookSnapshot,
    *,
    limit: int = 8,
) -> list[str]:
    if not outlook.rows:
        return []
    kind_label = "概念" if outlook.sector_kind == "concept" else "行业"
    lines = [f"未来{len(outlook.forward_dates)}日{kind_label}AI情景展望（{outlook.disclaimer}）："]
    for row in outlook.rows[: max(1, limit)]:
        day_labels = " / ".join(f"{day.bias}{day.strength:.2f}" for day in row.days)
        lines.append(f"- {row.sector.name} {day_labels} · {row.headline_pattern}")
    return lines


__all__ = [
    "attach_llm_outlook",
    "build_llm_outlook_empty",
    "build_llm_outlook_prompt",
    "format_llm_ai_lines",
    "generate_llm_outlook",
    "load_llm_outlook_from_cache",
    "outlook_bundle_fingerprint",
    "parse_llm_outlook_response",
]
