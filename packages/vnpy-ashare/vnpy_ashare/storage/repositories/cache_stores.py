"""cache schema 表 Repository。"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.storage.repository.cache import CacheBaseRepository
from vnpy_common.storage.compat import DbConnection, DbRow
from vnpy_common.storage.tables.cache import (
    radar_ai_hint_cache,
    radar_card_snapshot,
    radar_horizon_cache,
    radar_predict_cache,
    sector_flow_outlook_llm_cache,
    watchlist_position_cache,
    watchlist_signal_cache,
)


class RadarAiHintCacheRepository(CacheBaseRepository):
    table = radar_ai_hint_cache

    def get_hint_if_fresh(self, cache_key: str, *, now_text: str) -> str | None:
        row = self.fetchone(
            select(radar_ai_hint_cache.c.hint).where(
                radar_ai_hint_cache.c.cache_key == cache_key,
                radar_ai_hint_cache.c.expires_at > now_text,
            )
        )
        if row is None:
            return None
        return str(row["hint"] or "").strip() or None

    def upsert(
        self,
        *,
        cache_key: str,
        card_id: str,
        variant: str,
        fingerprint: str,
        hint: str,
        updated_at: str,
        expires_at: str,
    ) -> None:
        values = {
            "cache_key": cache_key,
            "card_id": card_id,
            "variant": variant,
            "fingerprint": fingerprint,
            "hint": hint,
            "updated_at": updated_at,
            "expires_at": expires_at,
        }

        def _write(conn: DbConnection) -> None:
            stmt = pg_insert(radar_ai_hint_cache).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[radar_ai_hint_cache.c.cache_key],
                    set_={
                        "hint": excluded.hint,
                        "updated_at": excluded.updated_at,
                        "expires_at": excluded.expires_at,
                    },
                )
            )

        self.run(_write)

    def delete_expired_before(self, cutoff: str) -> int:
        with self.session() as conn:
            cur = conn.execute_stmt(delete(radar_ai_hint_cache).where(radar_ai_hint_cache.c.expires_at <= cutoff))
            return int(cur.rowcount or 0)


class RadarHorizonCacheRepository(CacheBaseRepository):
    table = radar_horizon_cache

    def get_row(self, storage_key: str) -> DbRow | None:
        return self.fetchone(select(radar_horizon_cache).where(radar_horizon_cache.c.variant == storage_key))

    def upsert(
        self,
        *,
        storage_key: str,
        rows_json: str,
        scanned_total: int,
        excluded_count: int,
        prefilter_total: int,
        refined_total: int,
        kline_missing: int,
        strategy_key: str,
        computed_at: str,
    ) -> None:
        values = {
            "variant": storage_key,
            "rows_json": rows_json,
            "scanned_total": scanned_total,
            "excluded_count": excluded_count,
            "prefilter_total": prefilter_total,
            "refined_total": refined_total,
            "kline_missing": kline_missing,
            "strategy_key": strategy_key,
            "computed_at": computed_at,
        }

        def _write(conn: DbConnection) -> None:
            stmt = pg_insert(radar_horizon_cache).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[radar_horizon_cache.c.variant],
                    set_={
                        "rows_json": excluded.rows_json,
                        "scanned_total": excluded.scanned_total,
                        "excluded_count": excluded.excluded_count,
                        "prefilter_total": excluded.prefilter_total,
                        "refined_total": excluded.refined_total,
                        "kline_missing": excluded.kline_missing,
                        "strategy_key": excluded.strategy_key,
                        "computed_at": excluded.computed_at,
                    },
                )
            )

        self.run(_write)

    def delete_computed_before(self, cutoff: str) -> int:
        with self.session() as conn:
            cur = conn.execute_stmt(delete(radar_horizon_cache).where(radar_horizon_cache.c.computed_at < cutoff))
            return int(cur.rowcount or 0)


class RadarPredictCacheRepository(CacheBaseRepository):
    table = radar_predict_cache

    def get_row(self, variant: str) -> DbRow | None:
        return self.fetchone(select(radar_predict_cache).where(radar_predict_cache.c.variant == variant))

    def upsert(
        self,
        *,
        variant: str,
        rows_json: str,
        scanned_total: int,
        excluded_count: int,
        prefilter_total: int,
        refined_total: int,
        kline_missing: int,
        model_label: str,
        computed_at: str,
    ) -> None:
        values = {
            "variant": variant,
            "rows_json": rows_json,
            "scanned_total": scanned_total,
            "excluded_count": excluded_count,
            "prefilter_total": prefilter_total,
            "refined_total": refined_total,
            "kline_missing": kline_missing,
            "model_label": model_label,
            "computed_at": computed_at,
        }

        def _write(conn: DbConnection) -> None:
            stmt = pg_insert(radar_predict_cache).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[radar_predict_cache.c.variant],
                    set_={
                        "rows_json": excluded.rows_json,
                        "scanned_total": excluded.scanned_total,
                        "excluded_count": excluded.excluded_count,
                        "prefilter_total": excluded.prefilter_total,
                        "refined_total": excluded.refined_total,
                        "kline_missing": excluded.kline_missing,
                        "model_label": excluded.model_label,
                        "computed_at": excluded.computed_at,
                    },
                )
            )

        self.run(_write)

    def delete_computed_before(self, cutoff: str) -> int:
        with self.session() as conn:
            cur = conn.execute_stmt(delete(radar_predict_cache).where(radar_predict_cache.c.computed_at < cutoff))
            return int(cur.rowcount or 0)


class RadarCardSnapshotRepository(CacheBaseRepository):
    table = radar_card_snapshot

    def get_row(self, card_id: str, variant_key: str) -> DbRow | None:
        return self.fetchone(
            select(radar_card_snapshot.c.payload_json, radar_card_snapshot.c.computed_at).where(
                radar_card_snapshot.c.card_id == card_id,
                radar_card_snapshot.c.variant_key == variant_key,
            )
        )

    def upsert(self, *, card_id: str, variant_key: str, payload_json: str, computed_at: str) -> None:
        values = {
            "card_id": card_id,
            "variant_key": variant_key,
            "payload_json": payload_json,
            "computed_at": computed_at,
        }

        def _write(conn: DbConnection) -> None:
            stmt = pg_insert(radar_card_snapshot).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[radar_card_snapshot.c.card_id, radar_card_snapshot.c.variant_key],
                    set_={"payload_json": excluded.payload_json, "computed_at": excluded.computed_at},
                )
            )

        self.run(_write)

    def clear_all(self) -> None:
        with self.session() as conn:
            conn.execute_stmt(delete(radar_card_snapshot))


class SectorFlowOutlookLlmCacheRepository(CacheBaseRepository):
    table = sector_flow_outlook_llm_cache

    def get_row_if_fresh(self, cache_key: str, *, now_text: str) -> DbRow | None:
        return self.fetchone(
            select(sector_flow_outlook_llm_cache).where(
                sector_flow_outlook_llm_cache.c.cache_key == cache_key,
                sector_flow_outlook_llm_cache.c.expires_at > now_text,
            )
        )

    def upsert(
        self,
        *,
        cache_key: str,
        sector_kind: str,
        strategy_key: str,
        fingerprint: str,
        forward_dates_json: str,
        rows_json: str,
        updated_at: str,
        expires_at: str,
    ) -> None:
        values = {
            "cache_key": cache_key,
            "sector_kind": sector_kind,
            "strategy_key": strategy_key,
            "fingerprint": fingerprint,
            "forward_dates_json": forward_dates_json,
            "rows_json": rows_json,
            "updated_at": updated_at,
            "expires_at": expires_at,
        }

        def _write(conn: DbConnection) -> None:
            stmt = pg_insert(sector_flow_outlook_llm_cache).values(values)
            excluded = stmt.excluded
            conn.execute_stmt(
                stmt.on_conflict_do_update(
                    index_elements=[sector_flow_outlook_llm_cache.c.cache_key],
                    set_={
                        "forward_dates_json": excluded.forward_dates_json,
                        "rows_json": excluded.rows_json,
                        "updated_at": excluded.updated_at,
                        "expires_at": excluded.expires_at,
                    },
                )
            )

        self.run(_write)

    def delete_expired_before(self, cutoff: str) -> int:
        with self.session() as conn:
            cur = conn.execute_stmt(delete(sector_flow_outlook_llm_cache).where(sector_flow_outlook_llm_cache.c.expires_at <= cutoff))
            return int(cur.rowcount or 0)


class WatchlistSignalCacheRepository(CacheBaseRepository):
    table = watchlist_signal_cache

    def delete_updated_before(self, cutoff: str) -> int:
        with self.session() as conn:
            cur = conn.execute_stmt(delete(watchlist_signal_cache).where(watchlist_signal_cache.c.updated_at < cutoff))
            return int(cur.rowcount or 0)


class WatchlistPositionCacheRepository(CacheBaseRepository):
    table = watchlist_position_cache

    def delete_updated_before(self, cutoff: str) -> int:
        with self.session() as conn:
            cur = conn.execute_stmt(delete(watchlist_position_cache).where(watchlist_position_cache.c.updated_at < cutoff))
            return int(cur.rowcount or 0)


_radar_ai_hint_repo = RadarAiHintCacheRepository()
_radar_horizon_repo = RadarHorizonCacheRepository()
_radar_predict_repo = RadarPredictCacheRepository()
_radar_card_snapshot_repo = RadarCardSnapshotRepository()
_sector_outlook_repo = SectorFlowOutlookLlmCacheRepository()
_signal_cache_repo = WatchlistSignalCacheRepository()
_position_cache_repo = WatchlistPositionCacheRepository()
