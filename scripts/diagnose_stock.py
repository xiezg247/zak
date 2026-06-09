#!/usr/bin/env python3
"""单股综合诊断 CLI（技术面 + 研报）"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData

from vnpy_ashare.paths import ENV_FILE

load_dotenv(ENV_FILE)


def load_daily_bars(symbol: str, exchange: Exchange) -> list[BarData]:
    db = get_database()
    bars: list[BarData] = db.load_bar_data(
        symbol=symbol,
        exchange=exchange,
        interval=Interval.DAILY,
        start=datetime(2010, 1, 1),
        end=datetime.now(),
    )
    # 按时间排序
    bars.sort(key=lambda b: b.datetime)
    return bars


def describe_ma_alignment(
    last_close: float,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    ma60: float | None,
) -> str:
    if ma5 is None or ma20 is None:
        return "数据不足，无法判断均线排列"
    if ma5 > ma10 > ma20:
        trend = "短期多头排列"
    elif ma5 < ma10 < ma20:
        trend = "短期空头排列"
    else:
        trend = "均线交织"
    above = "站上" if last_close >= ma20 else "跌破"
    detail = f"{trend}，现价{above} MA20"
    if ma60 is not None:
        detail += f"，{'站上' if last_close >= ma60 else '跌破'} MA60"
    return detail


def technical_snapshot(symbol: str, exchange: Exchange, lookback: int = 60) -> dict[str, Any]:
    bars = load_daily_bars(symbol, exchange)
    warnings: list[str] = []

    if len(bars) < 2:
        return {
            "symbol": f"{symbol}.{exchange.value}",
            "warnings": ["本地暂无足够 K 线，请先下载日 K 数据"],
            "sources": ["bar"],
            "as_of": datetime.now().strftime("%Y-%m-%d"),
        }

    tail = bars[-lookback:] if len(bars) >= lookback else bars
    closes = [bar.close_price for bar in tail]
    volumes = [bar.volume for bar in tail]
    last_close = closes[-1]

    def _ma(window: int) -> float | None:
        if len(closes) < window:
            return None
        segment = closes[-window:]
        return round(sum(segment) / len(segment), 2)

    ma5, ma10, ma20, ma60 = _ma(5), _ma(10), _ma(20), _ma(60)
    ma_alignment = describe_ma_alignment(last_close, ma5, ma10, ma20, ma60)

    # 量比
    recent_vol = volumes[-5:] if len(volumes) >= 5 else volumes
    base_vol = volumes[:-5] if len(volumes) > 10 else volumes
    avg_recent = sum(recent_vol) / len(recent_vol) if recent_vol else 0
    avg_base = sum(base_vol) / len(base_vol) if base_vol else avg_recent
    volume_ratio = round(avg_recent / avg_base, 2) if avg_base else None

    # 区间涨跌幅
    lookback_days = min(lookback, 60)
    period_tail = bars[-lookback_days:] if len(bars) >= lookback_days else bars
    first_close = period_tail[0].close_price
    return_pct = round((last_close - first_close) / first_close * 100, 2)

    return {
        "symbol": f"{symbol}.{exchange.value}",
        "scope": "daily",
        "as_of": tail[-1].datetime.strftime("%Y-%m-%d"),
        "bars_used": len(tail),
        "last_close": round(last_close, 2),
        "ma": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60},
        "ma_alignment": ma_alignment,
        "volume_ratio_5d": volume_ratio,
        f"return_{lookback_days}d_pct": return_pct,
        "sources": ["bar"],
        "warnings": warnings,
    }


def fetch_mcp_reports(symbol: str, exchange: Exchange) -> dict[str, Any]:
    """通过通达信 MCP 获取研报。"""
    from vnpy_mcp.client import McpClientError, call_remote_tool, list_remote_tools
    from vnpy_mcp.config import load_all_mcp_servers

    configs = load_all_mcp_servers()
    if not configs:
        return {"reports": [], "warnings": ["通达信 MCP 未配置"]}

    tdx = configs.get("tdx")
    if not tdx or not tdx.available:
        return {"reports": [], "warnings": ["通达信 MCP 不可用"]}

    try:
        tools = list_remote_tools(tdx.url, tdx.headers, timeout=30)
    except McpClientError as ex:
        return {"reports": [], "warnings": [f"通达信 MCP 连接失败: {ex}"]}

    # 找研报/F10 工具
    report_tools = [t for t in tools if any(kw in t.name.lower() for kw in ("report", "research", "yanbao", "研报", "rating", "f10", "fundamental"))]
    if not report_tools:
        return {"reports": [], "warnings": [f"通达信 MCP 未提供研报工具（共 {len(tools)} 个工具）"]}

    tool = report_tools[0]
    vt_symbol = f"{symbol}.{exchange.value}"
    args: dict[str, Any] = {}
    if "code" in tool.name.lower() or "symbol" in tool.name.lower():
        args = {"code": symbol, "symbol": symbol, "stock_code": symbol}
    else:
        args = {"symbol": vt_symbol, "code": symbol}

    try:
        result = call_remote_tool(tdx.url, tdx.headers, tool.name, args, timeout=60)
    except McpClientError as ex:
        return {"reports": [], "warnings": [f"通达信 MCP 调用失败: {ex}"]}

    # 解析结果
    raw_text = ""
    if hasattr(result, "content"):
        for c in result.content:
            if hasattr(c, "text"):
                raw_text += c.text
    elif isinstance(result, str):
        raw_text = result
    else:
        raw_text = str(result)

    return {
        "reports": [{"title": f"通达信 MCP · {tool.name}", "summary": raw_text[:3000], "source": "tdx_mcp", "tool": tool.name}],
        "source": "tdx_mcp",
        "warnings": [],
    }


def describe_trend(return_pct: float, volatility_pct: float) -> str:
    if return_pct >= 5:
        base = "区间明显上行"
    elif return_pct <= -5:
        base = "区间明显下行"
    elif return_pct >= 1:
        base = "区间温和上行"
    elif return_pct <= -1:
        base = "区间温和下行"
    else:
        base = "区间横盘震荡"
    if volatility_pct >= 3:
        return f"{base}，波动偏大"
    if volatility_pct <= 1:
        return f"{base}，波动偏低"
    return base


def historical_summary(symbol: str, exchange: Exchange, lookback: int = 20) -> dict[str, Any]:
    bars = load_daily_bars(symbol, exchange)
    if len(bars) < lookback:
        return {
            "symbol": f"{symbol}.{exchange.value}",
            "warnings": ["本地 K 线不足"],
            "sources": ["bar"],
        }

    tail = bars[-lookback:]
    closes = [bar.close_price for bar in tail]
    highs = [bar.high_price for bar in tail]
    lows = [bar.low_price for bar in tail]
    first_close = closes[0]
    last_close = closes[-1]
    return_pct = round((last_close - first_close) / first_close * 100, 2)

    daily_changes: list[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev:
            daily_changes.append((closes[i] - prev) / prev * 100)

    volatility_pct = 0.0
    if len(daily_changes) >= 2:
        mean_change = sum(daily_changes) / len(daily_changes)
        variance = sum((v - mean_change) ** 2 for v in daily_changes) / len(daily_changes)
        volatility_pct = round(variance**0.5, 2)

    up_streak = down_streak = 0
    max_up = max_down = 0
    for change in daily_changes:
        if change > 0:
            up_streak += 1
            down_streak = 0
        elif change < 0:
            down_streak += 1
            up_streak = 0
        else:
            up_streak = down_streak = 0
        max_up = max(max_up, up_streak)
        max_down = max(max_down, down_streak)

    trend_label = describe_trend(return_pct, volatility_pct)

    return {
        "symbol": f"{symbol}.{exchange.value}",
        "scope": "daily",
        "lookback_days": len(tail),
        "start": tail[0].datetime.strftime("%Y-%m-%d"),
        "end": tail[-1].datetime.strftime("%Y-%m-%d"),
        "return_pct": return_pct,
        "close_start": round(first_close, 2),
        "close_end": round(last_close, 2),
        "high": round(max(highs), 2),
        "low": round(min(lows), 2),
        "volatility_pct": volatility_pct,
        "max_consecutive_up_days": max_up,
        "max_consecutive_down_days": max_down,
        "trend_label": trend_label,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="单股综合诊断")
    parser.add_argument("--symbol", required=True, help="股票代码，如 002230")
    parser.add_argument("--exchange", default="SZSE", choices=["SSE", "SZSE", "BSE"], help="交易所")
    parser.add_argument("--no-reports", action="store_true", help="跳过研报查询")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = parser.parse_args()

    exchange = Exchange[args.exchange]
    symbol = args.symbol

    # 技术面
    tech = technical_snapshot(symbol, exchange, lookback=60)

    # 历史走势
    hist = historical_summary(symbol, exchange, lookback=20)

    # 研报
    reports_data: dict[str, Any] = {"reports": [], "warnings": []}
    if not args.no_reports:
        reports_data = fetch_mcp_reports(symbol, exchange)

    result = {
        "symbol": f"{symbol}.{exchange.value}",
        "name": "科大讯飞" if symbol == "002230" else symbol,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "technical": tech,
        "historical_20d": hist,
        "reports": reports_data.get("reports", []),
        "report_warnings": reports_data.get("warnings", []),
        "disclaimer": "以上内容来自工具数据与第三方研报摘要，不构成投资建议。",
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # 格式化输出
    print("=" * 64)
    print("  📊 科大讯飞 (002230.SZSE) 综合诊断报告")
    print(f"  生成时间：{result['as_of']}")
    print("=" * 64)

    print("\n── 技术面 ──")
    print(f"  最新收盘价：{tech.get('last_close')}")
    print(f"  均线排列：{tech.get('ma_alignment')}")
    ma = tech.get("ma", {})
    print(f"  均线值：MA5={ma.get('ma5')}  MA10={ma.get('ma10')}  MA20={ma.get('ma20')}  MA60={ma.get('ma60')}")
    print(f"  5日量比：{tech.get('volume_ratio_5d')}")
    return_key = [k for k in tech if k.startswith("return_")]
    if return_key:
        print(f"  区间涨跌：{return_key[0]} = {tech.get(return_key[0])}%")

    print("\n── 近20日走势 ──")
    print(f"  区间：{hist.get('start')} → {hist.get('end')}")
    print(f"  涨跌幅：{hist.get('return_pct')}%")
    print(f"  波动率：{hist.get('volatility_pct')}%")
    print(f"  最高：{hist.get('high')}  最低：{hist.get('low')}")
    print(f"  最长连涨：{hist.get('max_consecutive_up_days')}天  最长连跌：{hist.get('max_consecutive_down_days')}天")
    print(f"  趋势标签：{hist.get('trend_label')}")

    if reports_data.get("reports"):
        print("\n── 券商研报 ──")
        for r in reports_data["reports"]:
            print(f"  来源：{r.get('source', '')} · {r.get('tool', '')}")
            print(f"  标题：{r.get('title', '')}")
            if r.get("summary"):
                print(f"  摘要：{r['summary'][:500]}")
    elif reports_data.get("warnings"):
        print("\n── 研报 ──")
        for w in reports_data["warnings"]:
            print(f"  ⚠️ {w}")

    print(f"\n{result['disclaimer']}")
    print("=" * 64)

    # 输出 JSON 供程序化使用
    print("\n--- RAW JSON ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
