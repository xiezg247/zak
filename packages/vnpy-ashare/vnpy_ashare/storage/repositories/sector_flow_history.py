"""板块资金日终历史（供详情页近 N 日柱状图）。"""

from __future__ import annotations

from sqlalchemy import select

from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint, SectorFlowRow
from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.storage.repository import bulk_upsert
from vnpy_common.storage.tables import sector_flow_daily as sfd

_HISTORY_LIMIT = 15
_ROTATION_DAYS = 15

_UPSERT_UPDATE_COLUMNS = ("name", "change_pct", "net_flow_yi", "flow_source")


class SectorFlowDailyRepository(AppBaseRepository):
    table = sfd

    def upsert_day(self, trade_date: str, sector_kind: str, rows: list[SectorFlowRow]) -> None:
        date_key = str(trade_date or "").strip()
        kind = str(sector_kind or "industry").strip().lower()
        if not date_key or not rows:
            return
        values = [
            {
                "trade_date": date_key,
                "sector_kind": kind,
                "sector_id": row.sector_id,
                "name": row.name,
                "change_pct": row.change_pct,
                "net_flow_yi": row.net_flow_yi,
                "flow_source": row.flow_source,
            }
            for row in rows
        ]

        def _write(conn) -> None:
            bulk_upsert(
                conn,
                self.table,
                values,
                conflict_columns=("trade_date", "sector_kind", "sector_id"),
                update_columns=_UPSERT_UPDATE_COLUMNS,
            )

        self.run(_write)

    def load_history(
        self,
        *,
        sector_id: str,
        sector_kind: str,
        limit: int = _HISTORY_LIMIT,
    ) -> list[SectorFlowHistoryPoint]:
        sid = str(sector_id or "").strip()
        kind = str(sector_kind or "industry").strip().lower()
        if not sid:
            return []
        rows = self.fetchall(
            select(sfd.c.trade_date, sfd.c.net_flow_yi)
            .where(sfd.c.sector_kind == kind, sfd.c.sector_id == sid)
            .order_by(sfd.c.trade_date.desc())
            .limit(max(1, limit))
        )
        points = [
            SectorFlowHistoryPoint(
                trade_date=str(row["trade_date"]),
                net_flow_yi=float(row["net_flow_yi"] or 0),
            )
            for row in rows
        ]
        points.reverse()
        return points

    def load_matrix(
        self,
        *,
        sector_kind: str,
        trade_dates: list[str],
        sector_ids: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        kind = str(sector_kind or "industry").strip().lower()
        dates = [str(item or "").strip() for item in trade_dates if str(item or "").strip()]
        if not dates:
            return {}
        ids = [str(item or "").strip() for item in (sector_ids or []) if str(item or "").strip()]
        stmt = select(sfd.c.sector_id, sfd.c.trade_date, sfd.c.net_flow_yi).where(
            sfd.c.sector_kind == kind,
            sfd.c.trade_date.in_(dates),
        )
        if ids:
            stmt = stmt.where(sfd.c.sector_id.in_(ids))
        rows = self.fetchall(stmt)
        matrix: dict[str, dict[str, float]] = {}
        for row in rows:
            sector_id = str(row["sector_id"] or "").strip()
            trade_date = str(row["trade_date"] or "").strip()
            if not sector_id or not trade_date:
                continue
            matrix.setdefault(sector_id, {})[trade_date] = float(row["net_flow_yi"] or 0)
        return matrix


_repo = SectorFlowDailyRepository()


def upsert_sector_flow_day(trade_date: str, sector_kind: str, rows: list[SectorFlowRow]) -> None:
    _repo.upsert_day(trade_date, sector_kind, rows)


def load_sector_flow_history(
    *,
    sector_id: str,
    sector_kind: str,
    limit: int = _HISTORY_LIMIT,
) -> list[SectorFlowHistoryPoint]:
    return _repo.load_history(sector_id=sector_id, sector_kind=sector_kind, limit=limit)


def load_sector_flow_matrix(
    *,
    sector_kind: str,
    trade_dates: list[str],
    sector_ids: list[str] | None = None,
) -> dict[str, dict[str, float]]:
    return _repo.load_matrix(sector_kind=sector_kind, trade_dates=trade_dates, sector_ids=sector_ids)


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
