"""板块资金概览：盘中采样与快照构建。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from vnpy_ashare.domain.market.sector_flow import (
    SectorFlowIntradayPoint,
    SectorFlowOverviewSeries,
    SectorFlowOverviewSnapshot,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.domain.time.china import format_china_date
from vnpy_ashare.domain.time.market_hours import (
    AFTERNOON_CLOSE_MIN,
    AFTERNOON_OPEN_MIN,
    CHINA_TZ,
    MORNING_CLOSE_MIN,
    MORNING_OPEN_MIN,
    is_ashare_trading_session,
)
from vnpy_ashare.storage.repositories.sector_flow_intraday import (
    SectorFlowIntradayRecord,
    load_intraday_records,
    purge_intraday_before,
    upsert_intraday_samples,
)

OVERVIEW_TOP_EACH_SIDE = 8
_BUCKET_MINUTES = 5


def _to_china_time(dt: datetime | None = None) -> datetime:
    if dt is None:
        return datetime.now(CHINA_TZ)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CHINA_TZ)
    return dt.astimezone(CHINA_TZ)


def intraday_bucket_time(dt: datetime | None = None) -> tuple[str, int]:
    """对齐到 5 分钟桶，并限制在 A 股连续竞价时段内。"""
    now = _to_china_time(dt)
    minutes = now.hour * 60 + now.minute
    if minutes < MORNING_OPEN_MIN:
        minutes = MORNING_OPEN_MIN
    elif MORNING_CLOSE_MIN < minutes < AFTERNOON_OPEN_MIN:
        minutes = MORNING_CLOSE_MIN
    elif minutes > AFTERNOON_CLOSE_MIN:
        minutes = AFTERNOON_CLOSE_MIN
    aligned = (minutes // _BUCKET_MINUTES) * _BUCKET_MINUTES
    hour, minute = divmod(aligned, 60)
    return f"{hour:02d}:{minute:02d}", aligned


def _top_sample_rows(snapshot: SectorFlowSnapshot) -> list[SectorFlowRow]:
    inflow = list(snapshot.inflow_rows)[:OVERVIEW_TOP_EACH_SIDE]
    outflow = list(snapshot.outflow_rows)[:OVERVIEW_TOP_EACH_SIDE]
    seen: set[str] = set()
    merged: list[SectorFlowRow] = []
    for row in inflow + outflow:
        if row.sector_id in seen:
            continue
        seen.add(row.sector_id)
        merged.append(row)
    return merged


def record_intraday_overview_sample(snapshot: SectorFlowSnapshot, *, dt: datetime | None = None) -> None:
    """盘中 refresh 后写入 Top 板块采样。"""
    if snapshot.data_mode != "intraday" or not snapshot.rows:
        return
    if not is_ashare_trading_session(dt):
        return
    trade_date = (snapshot.trade_date or format_china_date())[:10]
    purge_intraday_before(trade_date)
    bucket_time, clock_minutes = intraday_bucket_time(dt)
    upsert_intraday_samples(
        trade_date,
        snapshot.sector_kind,
        _top_sample_rows(snapshot),
        bucket_time=bucket_time,
        clock_minutes=clock_minutes,
    )


def _series_from_records(
    sector_id: str,
    records: list[SectorFlowIntradayRecord],
    *,
    sector_kind: str,
) -> SectorFlowOverviewSeries | None:
    if not records:
        return None
    records = sorted(records, key=lambda item: item.clock_minutes)
    latest = records[-1]
    points = tuple(
        SectorFlowIntradayPoint(
            bucket_time=item.bucket_time,
            clock_minutes=item.clock_minutes,
            net_flow_yi=item.net_flow_yi,
        )
        for item in records
    )
    return SectorFlowOverviewSeries(
        sector_id=sector_id,
        name=latest.name,
        sector_kind=sector_kind,
        latest_yi=latest.net_flow_yi,
        change_pct=latest.change_pct,
        points=points,
    )


def _bar_series_from_row(row: SectorFlowRow) -> SectorFlowOverviewSeries:
    """日终/无曲线时：单点序列（横向榜数据源）。"""
    point = SectorFlowIntradayPoint(bucket_time="收盘", clock_minutes=AFTERNOON_CLOSE_MIN, net_flow_yi=row.net_flow_yi)
    return SectorFlowOverviewSeries(
        sector_id=row.sector_id,
        name=row.name,
        sector_kind=row.sector_kind,
        latest_yi=row.net_flow_yi,
        change_pct=row.change_pct,
        points=(point,),
    )


def _build_time_axis_from_records(records: list[SectorFlowIntradayRecord]) -> tuple[str, ...]:
    if not records:
        return ()
    seen: set[int] = set()
    ordered: list[int] = []
    for item in sorted(records, key=lambda row: row.clock_minutes):
        if item.clock_minutes in seen:
            continue
        seen.add(item.clock_minutes)
        ordered.append(item.clock_minutes)
    labels: list[str] = []
    for minute in ordered:
        hour, mod = divmod(minute, 60)
        labels.append(f"{hour:02d}:{mod:02d}")
    return tuple(labels)


def build_overview_snapshot(snapshot: SectorFlowSnapshot) -> SectorFlowOverviewSnapshot:
    """由当前快照 + 本地盘中采样构建概览。"""
    trade_date = (snapshot.trade_date or format_china_date())[:10]
    sector_kind = snapshot.sector_kind or "industry"
    positives = [row for row in snapshot.rows if row.net_flow_yi > 0]
    negatives = [row for row in snapshot.rows if row.net_flow_yi < 0]
    net_inflow_count = len(positives)
    net_outflow_count = len(negatives)

    if not snapshot.rows:
        return SectorFlowOverviewSnapshot(
            trade_date=trade_date,
            sector_kind=sector_kind,
            data_mode=snapshot.data_mode,
            updated_at=snapshot.updated_at or "",
            empty_hint=snapshot.empty_hint or "暂无板块数据",
        )

    records = load_intraday_records(trade_date=trade_date, sector_kind=sector_kind)
    grouped: dict[str, list[SectorFlowIntradayRecord]] = defaultdict(list)
    for item in records:
        grouped[item.sector_id].append(item)

    has_curve = bool(records) and snapshot.data_mode == "intraday"
    time_axis = _build_time_axis_from_records(records) if has_curve else ("收盘",)

    if has_curve:
        series_list = [_series_from_records(sid, items, sector_kind=sector_kind) for sid, items in grouped.items()]
        series_list = [item for item in series_list if item is not None]
        inflow_series = sorted(
            [item for item in series_list if item.latest_yi > 0],
            key=lambda item: item.latest_yi,
            reverse=True,
        )[:OVERVIEW_TOP_EACH_SIDE]
        outflow_series = sorted(
            [item for item in series_list if item.latest_yi < 0],
            key=lambda item: item.latest_yi,
        )[:OVERVIEW_TOP_EACH_SIDE]
    else:
        inflow_series = [_bar_series_from_row(row) for row in list(snapshot.inflow_rows)[:OVERVIEW_TOP_EACH_SIDE]]
        outflow_series = [_bar_series_from_row(row) for row in list(snapshot.outflow_rows)[:OVERVIEW_TOP_EACH_SIDE]]

    empty_hint = ""
    if not has_curve and snapshot.data_mode != "intraday":
        empty_hint = "日终官方数据：展示当日结果榜；盘中曲线需交易时段刷新积累"

    return SectorFlowOverviewSnapshot(
        trade_date=trade_date,
        sector_kind=sector_kind,
        data_mode=snapshot.data_mode,
        updated_at=snapshot.updated_at or "",
        time_axis=time_axis,
        inflow_series=tuple(inflow_series),
        outflow_series=tuple(outflow_series),
        top_inflow_name=snapshot.top_inflow_name,
        top_inflow_yi=snapshot.top_inflow_yi,
        top_outflow_name=snapshot.top_outflow_name,
        top_outflow_yi=snapshot.top_outflow_yi,
        net_inflow_count=net_inflow_count,
        net_outflow_count=net_outflow_count,
        has_intraday_curve=has_curve,
        empty_hint=empty_hint,
    )
