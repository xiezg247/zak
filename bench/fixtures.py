"""性能基准 synthetic 数据（不依赖 Redis / PostgreSQL）。"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_row import QuoteRow
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot


def make_synthetic_quote_snapshots(count: int = 5000) -> dict[str, QuoteSnapshot]:
    """生成全市场规模的假行情快照（TickFlow symbol 键）。"""
    quotes: dict[str, QuoteSnapshot] = {}
    for index in range(count):
        code = f"{index + 1:06d}"
        board = index % 3
        if board == 0:
            tf_symbol = f"{code}.SH"
            name = f"沪A{code}"
        elif board == 1:
            tf_symbol = f"{code}.SZ"
            name = f"深A{code}"
        else:
            tf_symbol = f"3{code[1:]}.SZ"
            name = f"创{code}"
        change_pct = (index % 200 - 100) / 10.0
        last = 10.0 + change_pct * 0.1
        quotes[tf_symbol] = QuoteSnapshot(
            symbol=code,
            name=name,
            last_price=last,
            prev_close=10.0,
            open_price=10.0,
            high_price=last + 0.2,
            low_price=last - 0.2,
            change_amount=last - 10.0,
            change_pct=change_pct,
            turnover_rate=float(index % 30),
            volume=float(1_000_000 + index * 100),
            amount=float(50_000_000 + index * 10_000),
            amplitude=abs(change_pct) + 1.0,
            volume_ratio=float(1 + (index % 50) / 10),
            net_mf_amount=float((index % 100) - 50),
            change_speed_5m=float((index % 20) - 10) / 10,
            limit_times=float(index % 5),
            trade_time="2026-06-26 10:30:00",
        )
    return quotes


def make_synthetic_quote_rows(count: int = 5000) -> list[QuoteRow]:
    """生成选股管道可用的 QuoteRow 列表。"""
    rows: list[QuoteRow] = []
    for index in range(count):
        code = f"{index + 1:06d}"
        exchange = "SSE" if index % 2 == 0 else "SZSE"
        vt_symbol = f"{code}.{exchange}"
        change_pct = (index % 200 - 100) / 10.0
        last = 10.0 + change_pct * 0.1
        rows.append(
            QuoteRow(
                symbol=code,
                name=f"测试{code}",
                vt_symbol=vt_symbol,
                exchange=exchange,
                last_price=last,
                prev_close=10.0,
                open_price=10.0,
                high_price=last + 0.2,
                low_price=last - 0.2,
                change_pct=change_pct,
                change_amount=last - 10.0,
                turnover_rate=float(index % 30),
                volume=float(1_000_000 + index * 100),
                amount=float(50_000_000 + index * 10_000),
                volume_ratio=float(1 + (index % 50) / 10),
                net_mf_amount=float((index % 100) - 50),
                limit_times=float(index % 5),
                amplitude=abs(change_pct) + 1.0,
                close=last,
            )
        )
    return rows
