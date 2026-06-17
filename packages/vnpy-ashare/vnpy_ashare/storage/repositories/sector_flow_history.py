"""板块资金日终历史（供详情页近 N 日柱状图）。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint, SectorFlowRow
from vnpy_ashare.storage.connection import connect, init_app_db

_HISTORY_LIMIT = 5


def upsert_sector_flow_day(
    trade_date: str,
    sector_kind: str,
    rows: list[SectorFlowRow],
) -> None:
    """写入单日板块资金快照（官方日终数据）。"""
    date_key = str(trade_date or "").strip()
    kind = str(sector_kind or "industry").strip().lower()
    if not date_key or not rows:
        return
    init_app_db()
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO sector_flow_daily(
                trade_date, sector_kind, sector_id, name, change_pct, net_flow_yi, flow_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date, sector_kind, sector_id) DO UPDATE SET
                name = excluded.name,
                change_pct = excluded.change_pct,
                net_flow_yi = excluded.net_flow_yi,
                flow_source = excluded.flow_source
            """,
            [
                (
                    date_key,
                    kind,
                    row.sector_id,
                    row.name,
                    row.change_pct,
                    row.net_flow_yi,
                    row.flow_source,
                )
                for row in rows
            ],
        )


def load_sector_flow_history(
    *,
    sector_id: str,
    sector_kind: str,
    limit: int = _HISTORY_LIMIT,
) -> list[SectorFlowHistoryPoint]:
    """读取板块近 N 个交易日主力净流入（升序）。"""
    sid = str(sector_id or "").strip()
    kind = str(sector_kind or "industry").strip().lower()
    if not sid:
        return []
    init_app_db()
    with connect() as conn:
        cursor = conn.execute(
            """
            SELECT trade_date, net_flow_yi
            FROM sector_flow_daily
            WHERE sector_kind = ? AND sector_id = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (kind, sid, max(1, limit)),
        )
        rows = list(cursor.fetchall())
    points = [
        SectorFlowHistoryPoint(
            trade_date=str(row["trade_date"]),
            net_flow_yi=float(row["net_flow_yi"] or 0),
        )
        for row in rows
    ]
    points.reverse()
    return points


def merge_sector_flow_history(
    local: list[SectorFlowHistoryPoint],
    remote: list[SectorFlowHistoryPoint],
    *,
    limit: int = _HISTORY_LIMIT,
) -> list[SectorFlowHistoryPoint]:
    """合并本地与 Tushare 回填历史，按交易日升序取近 limit 条。"""
    by_date: dict[str, SectorFlowHistoryPoint] = {point.trade_date: point for point in remote if point.trade_date}
    for point in local:
        if point.trade_date:
            by_date[point.trade_date] = point
    merged = sorted(by_date.values(), key=lambda item: item.trade_date)
    return merged[-max(1, limit) :]


def upsert_sector_history_points(sector: SectorFlowRow, points: list[SectorFlowHistoryPoint]) -> None:
    """将回填的历史点写入本地库。"""
    for point in points:
        if not point.trade_date:
            continue
        row = SectorFlowRow(
            sector_id=sector.sector_id,
            name=sector.name,
            strength=sector.strength,
            change_pct=sector.change_pct,
            net_flow_yi=point.net_flow_yi,
            stock_count=sector.stock_count,
            up_ratio=sector.up_ratio,
            flow_source=sector.flow_source,
            sector_kind=sector.sector_kind,
            leader_stock=sector.leader_stock,
            net_flow_rate=sector.net_flow_rate,
            divergence_kind=sector.divergence_kind,
        )
        upsert_sector_flow_day(point.trade_date, sector.sector_kind, [row])
