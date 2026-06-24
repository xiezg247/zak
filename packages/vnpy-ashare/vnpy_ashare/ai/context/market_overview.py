"""市场页大盘概览 AI 上下文。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context.store import get_market_overview_context, set_market_overview_context
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.integrations.tushare.sw_industry import format_industry_filter_label
from vnpy_ashare.quotes.market.emotion_cycle import EmotionCycleSnapshot, format_mode_label
from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot
from vnpy_ashare.quotes.market.market_environment import MarketEnvironmentSnapshot, format_north_money_hsgt
from vnpy_ashare.quotes.market.market_overview_loaders import MarketOverviewData, SectorRankItem
from vnpy_common.ai.protocol import QuickAction


def _format_amount(amount: float) -> str:
    if amount <= 0:
        return "—"
    if amount >= 1e8:
        return f"{amount / 1e8:.2f}亿"
    if amount >= 1e4:
        return f"{amount / 1e4:.2f}万"
    return f"{amount:.2f}"


def build_market_environment_prompt() -> str:
    return build_market_ai_prompt(focus="environment")


def build_intraday_environment_prompt() -> str:
    return build_market_ai_prompt(focus="intraday")


def build_market_ai_prompt(*, focus: str = "intraday") -> str:
    """市场页 AI 预填：广度 + 情绪周期摘要。"""
    ctx = get_market_overview_context() or {}
    if focus == "environment":
        intro = (
            "请解读当前 A 股市场环境（大盘强弱、涨跌广度、涨跌停、成交额、恐贪指数、北向资金）。"
            "须结合 get_ashare_fear_greed_index 与 get_emotion_cycle；勿编造未在工具结果或摘要中的数据。"
        )
    else:
        intro = (
            "请评估今日 A 股极致短线交易环境，回答："
            "1) 当前是否适合新开仓及建议总仓位；"
            "2) 涨跌停与连板结构反映的情绪阶段；"
            "3) 行业强弱与可能主线；"
            "4) 需规避的风险（退潮、成交额不足、监管异动等）。"
            "须调用 get_emotion_cycle、get_ashare_fear_greed_index 补充；勿编造。"
        )
    lines = [intro, "", "## 终端已注入摘要"]
    overview = format_market_overview_extra(ctx)
    if overview:
        lines.append(overview)
    if len(lines) <= 3:
        lines.append("（摘要暂无，请先刷新市场页后再问 AI）")
    return "\n".join(lines).strip()


def build_industry_momentum_prompt() -> str:
    return "请解读当前 A 股行业轮动：哪些行业偏强/偏弱、与大盘广度的关系、对选股的启示。可结合终端已注入的行业榜摘要；不要编造未在摘要或工具结果中的板块数据。"


def build_market_page_quick_actions() -> list[QuickAction]:
    return [
        QuickAction(
            id="market_environment",
            label="大盘环境",
            auto_send=True,
            tooltip="解读指数、广度、恐贪与北向",
            prompt=build_market_environment_prompt(),
        ),
        QuickAction(
            id="intraday_environment",
            label="今日短线环境",
            auto_send=True,
            tooltip="评估极致短线是否可做、连板结构与仓位建议",
            prompt=build_intraday_environment_prompt(),
        ),
        QuickAction(
            id="industry_momentum",
            label="行业轮动",
            auto_send=True,
            tooltip="解读行业榜强弱与轮动逻辑",
            prompt=build_industry_momentum_prompt(),
        ),
    ]


def _index_lines(indices: list[tuple[str, QuoteSnapshot]], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for label, quote in indices[:limit]:
        lines.append(f"{label} {quote.last_price:.2f} {quote.change_pct:+.2f}%")
    return lines


def _sector_lines(sectors: list[SectorRankItem], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in sectors[:limit]:
        label = format_industry_filter_label(item.industry, item.industry_l1)
        lines.append(f"{label} 均涨 {item.avg_change_pct:+.2f}%（{item.count} 只）")
    return lines


def _breadth_line(breadth: MarketBreadthSnapshot | None) -> str:
    if breadth is None:
        return "市场广度：暂无"
    limit_tag = "官方涨跌停" if breadth.limit_source == "tushare" else "近似涨跌停"
    return (
        f"广度：涨 {breadth.up} / 跌 {breadth.down} / 平 {breadth.flat}；"
        f"涨停 {breadth.limit_up} / 跌停 {breadth.limit_down}（{limit_tag}）；"
        f"成交额 {_format_amount(breadth.total_amount)}"
    )


def _environment_line(env: MarketEnvironmentSnapshot | None) -> str:
    if env is None:
        return "环境：暂无"
    parts: list[str] = []
    if env.fear_greed_index is not None:
        parts.append(f"恐贪 {env.fear_greed_index:.0f} {env.fear_greed_label or ''}".strip())
    if env.north_money is not None:
        suffix = f" @{env.north_trade_date}" if env.north_trade_date else ""
        parts.append(f"北向 {format_north_money_hsgt(env.north_money)}{suffix}")
    return "环境：" + ("；".join(parts) if parts else "暂无 Tushare 环境数据")


def _emotion_line(snapshot: EmotionCycleSnapshot | None) -> str:
    if snapshot is None:
        return ""
    pos_max = int(snapshot.position_pct_max * 100)
    pos_min = int(snapshot.position_pct_min * 100)
    if pos_max <= 0:
        pos_text = "建议空仓"
    elif pos_min == pos_max:
        pos_text = f"建议总仓位 {pos_max}%"
    else:
        pos_text = f"建议总仓位 {pos_min}–{pos_max}%"
    modes = "、".join(format_mode_label(mode) for mode in snapshot.allowed_modes) or "无"
    line = f"情绪周期：{snapshot.stage_label}；{pos_text}；允许模式 {modes}"
    if not snapshot.allow_new_positions:
        line += "；不建议短线新开仓"
    return line


def build_market_overview_payload(
    data: MarketOverviewData,
    *,
    environment: MarketEnvironmentSnapshot | None = None,
) -> dict[str, Any]:
    env = environment if environment is not None else data.environment
    return {
        "index_lines": _index_lines(data.indices),
        "sector_lines": _sector_lines(data.sectors),
        "breadth_line": _breadth_line(data.breadth),
        "environment_line": _environment_line(env),
        "emotion_line": "",
    }


def format_market_overview_extra(payload: dict[str, Any] | None = None) -> str:
    """格式化为 AiContextData.extra 片段。"""
    ctx = payload if payload is not None else get_market_overview_context()
    if not ctx:
        return ""
    lines = ["【大盘概览】"]
    index_lines = ctx.get("index_lines") or []
    if index_lines:
        lines.append("主要指数：" + "；".join(str(item) for item in index_lines))
    breadth_line = str(ctx.get("breadth_line") or "").strip()
    if breadth_line:
        lines.append(breadth_line)
    environment_line = str(ctx.get("environment_line") or "").strip()
    if environment_line:
        lines.append(environment_line)
    emotion_line = str(ctx.get("emotion_line") or "").strip()
    if emotion_line:
        lines.append(emotion_line)
    sector_lines = ctx.get("sector_lines") or []
    if sector_lines:
        lines.append("行业 Top：" + "；".join(str(item) for item in sector_lines))
    if len(lines) <= 1:
        return ""
    lines.append("解读大盘时可结合 get_ashare_fear_greed_index 与 get_emotion_cycle；勿编造未在摘要中的数据。")
    return "\n".join(lines)


def sync_market_overview_context(
    data: MarketOverviewData,
    *,
    environment: MarketEnvironmentSnapshot | None = None,
) -> None:
    """写入市场页大盘概览上下文（供 AI 与悬浮球读取）。"""
    env = environment if environment is not None else data.environment
    payload = build_market_overview_payload(data, environment=env)
    has_content = bool(payload.get("index_lines") or payload.get("sector_lines"))
    has_content |= "涨" in str(payload.get("breadth_line", ""))
    if env is not None and (env.fear_greed_index is not None or env.north_money is not None):
        has_content = True
    if not has_content:
        set_market_overview_context(None)
        return
    set_market_overview_context(payload)


def sync_emotion_cycle_context(snapshot: EmotionCycleSnapshot | None) -> None:
    payload = dict(get_market_overview_context() or {})
    payload["emotion_line"] = _emotion_line(snapshot)
    if not payload.get("emotion_line") and not payload.get("breadth_line") and not payload.get("index_lines"):
        return
    set_market_overview_context(payload)


def sync_market_overview_partial(
    *,
    breadth: MarketBreadthSnapshot | None = None,
    sectors: list[SectorRankItem] | None = None,
) -> None:
    """增量更新已发布的大盘概览（catalog 刷新时）。"""
    payload = dict(get_market_overview_context() or {})
    if breadth is not None:
        payload["breadth_line"] = _breadth_line(breadth)
    if sectors:
        payload["sector_lines"] = _sector_lines(sectors)
    if not payload:
        return
    set_market_overview_context(payload)


def merge_market_overview_extra(extra: str) -> str:
    """将大盘概览摘要 prepend 到已有 extra。"""
    overview = format_market_overview_extra()
    if not overview:
        return extra.strip()
    if not extra.strip():
        return overview
    return f"{overview}\n{extra.strip()}"
