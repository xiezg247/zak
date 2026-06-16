"""投研团队：研报持久化。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import quote

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.storage.repositories import stock_analysis_reports as reports_repo


def team_report_href(report_id: int, vt_symbol: str) -> str:
    return f"zak://team-report/{int(report_id)}?symbol={quote(vt_symbol, safe='.')}"


def persist_team_analysis_report(
    symbol: str,
    body: str,
    *,
    name: str = "",
    team_scores: dict[str, Any] | None = None,
) -> dict[str, str | int] | None:
    """将团队综合研判保存至 stock_analysis_reports（静默，无 UI 确认）。"""
    text = body.strip()
    if not text or "综合研判" not in text:
        return None

    item = parse_stock_symbol(symbol)
    if item is None:
        return None

    head = (name or item.name or item.symbol).strip()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"{head} · 投研团队 · {stamp}"

    context = {
        "scope": "team_analysis",
        "symbol": item.vt_symbol,
        "team_scores": team_scores or {},
    }

    return reports_repo.create_report(
        item.symbol,
        item.exchange,
        title=title,
        body=text,
        source_scope="team_analysis",
        context_json=json.dumps(context, ensure_ascii=False),
    )
