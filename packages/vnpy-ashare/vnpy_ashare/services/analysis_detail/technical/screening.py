"""选股结果解读上下文编排。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import get_screening_results
from vnpy_ashare.screener.run.run_diff import compute_run_diff
from vnpy_ashare.screener.run.run_store import find_previous_run_by_recipe, get_run
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution
from vnpy_ashare.services.analysis_detail.technical.base import _TechnicalAnalyzerBase


class TechnicalScreeningMixin(_TechnicalAnalyzerBase):
    def build_screening_context(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 0,
    ) -> dict[str, Any]:
        """读取选股结果；可选历史 run_id 与批量技术面快照。"""
        screening_svc = getattr(self._engine, "screening_service", None)

        condition: str
        updated_at: str | None
        rows: list[Any]
        source: str
        run_meta: dict[str, Any]

        if run_id:
            record = get_run(run_id.strip())
            if record is None:
                return {"message": f"选股历史 run 不存在：{run_id}"}
            condition = record.condition
            updated_at = record.created_at
            rows = list(record.rows)
            source = "history_run"
            run_meta = {
                "run_id": record.id,
                "source": record.source,
                "total_scanned": record.total_scanned,
            }
        else:
            ctx = screening_svc.get_screening_results() if screening_svc is not None else get_screening_results()
            if ctx is None:
                return {
                    "message": "暂无选股结果，请用户先在「选股」页运行方案，或提供 run_id",
                }
            condition = str(ctx.condition or "")
            raw_updated = ctx.updated_at
            updated_at = raw_updated if isinstance(raw_updated, str) else None
            rows = list(ctx.rows)
            source = "session"
            run_meta = {}

        preview = []
        for row in rows[:20]:
            preview.append(
                {
                    "vt_symbol": row.get("vt_symbol", ""),
                    "name": row.get("name", ""),
                    "change_pct": row.get("change_pct"),
                    "pe_ttm": row.get("pe_ttm"),
                    "net_mf_amount": row.get("net_mf_amount"),
                }
            )

        payload: dict[str, Any] = {
            "condition": condition,
            "count": len(rows),
            "updated_at": updated_at,
            "preview": preview,
            "source": source,
            **run_meta,
        }

        batch_n = max(0, min(int(batch_top_n or 0), 10))
        if batch_n > 0:
            snapshots: list[dict[str, Any]] = []
            for row in rows[:batch_n]:
                symbol = str(row.get("vt_symbol") or row.get("symbol") or "").strip()
                if not symbol:
                    continue
                snap = self.technical_snapshot(symbol, lookback=20)
                snapshots.append(
                    {
                        "vt_symbol": snap.get("symbol", symbol),
                        "name": row.get("name", snap.get("name", "")),
                        "ma_alignment": snap.get("ma_alignment"),
                        "last_close": snap.get("last_close"),
                        "period_return": snap.get("period_return"),
                        "warnings": snap.get("warnings") or [],
                    }
                )
            payload["batch_snapshots"] = snapshots
            payload["batch_top_n"] = batch_n

        return payload

    def build_screening_explanation(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 5,
    ) -> dict[str, Any]:
        """编排选股解读上下文：结果快照 + 板块分布 + 同配方 diff + 可选技术面。"""
        payload = self.build_screening_context(run_id=run_id, batch_top_n=batch_top_n)
        if payload.get("message") and not payload.get("count"):
            return payload

        rows: list[dict[str, Any]] = []
        recipe_id = ""
        if run_id:
            record = get_run(run_id.strip())
            if record is not None:
                rows = list(record.rows)
                recipe_id = str(record.config.get("recipe_id") or "")
                if record.config.get("run_diff"):
                    payload["run_diff"] = dict(record.config["run_diff"])
        else:
            screening_svc = getattr(self._engine, "screening_service", None)
            ctx = screening_svc.get_screening_results() if screening_svc is not None else get_screening_results()
            if ctx is not None:
                rows = list(ctx.rows)

        if rows:
            enriched = attach_industry(rows)
            payload["sector_distribution"] = compute_sector_distribution(enriched)
            preview = payload.get("preview") or []
            industry_by_vt = {str(r.get("vt_symbol") or ""): str(r.get("industry") or "") for r in enriched}
            for item in preview:
                if isinstance(item, dict):
                    vt = str(item.get("vt_symbol") or "")
                    if vt in industry_by_vt and industry_by_vt[vt]:
                        item["industry"] = industry_by_vt[vt]

        if recipe_id and "run_diff" not in payload:
            previous = find_previous_run_by_recipe(recipe_id, exclude_run_id=run_id or "")
            if previous is not None and rows:
                payload["run_diff"] = compute_run_diff(rows, previous.rows)
                payload["run_diff"]["previous_run_id"] = previous.id

        payload["interpretation_hints"] = [
            "先概括板块分布与新增/保留标的，再逐只解读 Top 标的",
            "单票深度分析可继续调用 diagnose_stock",
            "大盘环境可选 get_ashare_fear_greed_index",
            "禁止编造未在结果中的指标或标的",
        ]
        return payload
