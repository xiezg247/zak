"""个股笔记 Service。"""

from __future__ import annotations

import json
from pathlib import Path

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.models.stock_note import (
    StockAnalysisReport,
    StockNoteBundle,
    StockNoteEntry,
    StockNoteIndexRow,
    StockNoteMemo,
)
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage.repositories import stock_analysis_reports as reports_repo
from vnpy_ashare.storage.repositories import stock_notes as stock_notes_repo
from vnpy_ashare.storage.repositories.universe import load_universe_rows
from vnpy_ashare.storage.repositories.watchlist import load_watchlist_rows


class NoteService(BaseService):
    """备忘（文档式）与流水（日记式）统一门面。"""

    def list_index_rows(self) -> list[StockNoteIndexRow]:
        name_map = self._symbol_name_map()
        rows: list[StockNoteIndexRow] = []
        for row in stock_notes_repo.list_note_index_rows():
            symbol = str(row["symbol"])
            exchange = str(row["exchange"])
            name = name_map.get((symbol, exchange), "")
            rows.append(
                StockNoteIndexRow(
                    symbol=symbol,
                    exchange=exchange,
                    name=name,
                    memo_preview=str(row.get("memo_preview") or ""),
                    has_memo=bool(row.get("has_memo")),
                    entry_count=int(row.get("entry_count") or 0),
                    report_count=int(row.get("report_count") or 0),
                    memo_updated_at=str(row.get("memo_updated_at") or ""),
                    latest_entry_at=str(row.get("latest_entry_at") or ""),
                    latest_report_at=str(row.get("latest_report_at") or ""),
                    last_activity_at=str(row.get("last_activity_at") or ""),
                )
            )
        return rows

    @staticmethod
    def _symbol_name_map() -> dict[tuple[str, str], str]:

        mapping: dict[tuple[str, str], str] = {}
        for symbol, exchange, name in load_universe_rows():
            mapping[(symbol, exchange.name)] = name
        for symbol, exchange, name in load_watchlist_rows():
            if name:
                mapping[(symbol, exchange.name)] = name
        return mapping

    def get_bundle(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        entry_limit: int = 50,
    ) -> StockNoteBundle:
        memo_row = stock_notes_repo.load_memo(symbol, exchange)
        memo: StockNoteMemo | None = None
        if memo_row is not None:
            memo = StockNoteMemo(
                symbol=memo_row["symbol"],
                exchange=memo_row["exchange"],
                body=str(memo_row["body"]),
                updated_at=str(memo_row["updated_at"]),
            )
        entries = [
            StockNoteEntry(
                id=int(row["id"]),
                symbol=str(row["symbol"]),
                exchange=str(row["exchange"]),
                body=str(row["body"]),
                created_at=str(row["created_at"]),
            )
            for row in stock_notes_repo.list_entries(symbol, exchange, limit=entry_limit)
        ]
        return StockNoteBundle(
            symbol=symbol,
            exchange=exchange.name,
            memo=memo,
            entries=entries,
        )

    def upsert_memo(self, symbol: str, exchange: Exchange, body: str) -> None:
        stock_notes_repo.upsert_memo(symbol, exchange, body)

    def append_entry(self, symbol: str, exchange: Exchange, body: str) -> StockNoteEntry | None:
        row = stock_notes_repo.append_entry(symbol, exchange, body)
        if row is None:
            return None
        return StockNoteEntry(
            id=int(row["id"]),
            symbol=str(row["symbol"]),
            exchange=str(row["exchange"]),
            body=str(row["body"]),
            created_at=str(row["created_at"]),
        )

    def delete_entry(self, entry_id: int) -> bool:
        return stock_notes_repo.delete_entry(entry_id)

    def clear_notes(self, symbol: str, exchange: Exchange) -> dict[str, int]:
        return stock_notes_repo.clear_notes_for_symbol(symbol, exchange)

    def create_report(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        title: str,
        body: str,
        source_scope: str = "",
        context_json: str = "",
    ) -> StockAnalysisReport:
        row = reports_repo.create_report(
            symbol,
            exchange,
            title=title,
            body=body,
            source_scope=source_scope,
            context_json=context_json,
        )
        return _report_from_row(row)

    def list_reports(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        limit: int = 100,
    ) -> list[StockAnalysisReport]:
        return [_report_from_row(row) for row in reports_repo.list_reports(symbol, exchange, limit=limit)]

    def get_report(self, report_id: int) -> StockAnalysisReport | None:
        row = reports_repo.get_report(report_id)
        if row is None:
            return None
        return _report_from_row(row)

    def delete_report(self, report_id: int) -> bool:
        return reports_repo.delete_report(report_id)

    def format_markdown(
        self,
        bundle: StockNoteBundle,
        *,
        name: str = "",
        entry_limit: int = 200,
        report_limit: int = 50,
    ) -> str:
        title = name.strip() or bundle.symbol
        vt = f"{bundle.symbol}.{bundle.exchange}"
        lines = [f"# {vt} {title}", ""]
        if bundle.memo is not None and bundle.memo.body.strip():
            lines.append("## 备忘")
            lines.append(f"（updated_at: {bundle.memo.updated_at}）")
            lines.append("")
            lines.append(bundle.memo.body.strip())
            lines.append("")
        entries = bundle.entries[: max(1, entry_limit)]
        if entries:
            lines.append("## 流水")
            for entry in reversed(entries):
                lines.append(f"- {entry.created_at}  {entry.body}")
            lines.append("")
        exchange = Exchange[bundle.exchange]
        reports = self.list_reports(bundle.symbol, exchange, limit=report_limit)
        if reports:
            lines.append("## 分析报告")
            for report in reports:
                lines.append(f"### {report.title}（{report.created_at}）")
                if report.source_scope:
                    lines.append(f"scope: {report.source_scope}")
                lines.append("")
                lines.append(report.body.strip())
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def export_symbol_markdown(
        self,
        symbol: str,
        exchange: Exchange,
        out_dir: Path,
        *,
        name: str = "",
    ) -> Path | None:
        bundle = self.get_bundle(symbol, exchange, entry_limit=200)
        if not self._bundle_has_content(bundle):
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{symbol}.{exchange}.md"
        path.write_text(self.format_markdown(bundle, name=name), encoding="utf-8")
        return path

    def export_all_markdown(self, out_dir: Path) -> list[Path]:
        paths: list[Path] = []
        for symbol, exchange_name in stock_notes_repo.list_symbols_with_notes():
            exchange = Exchange[exchange_name]
            path = self.export_symbol_markdown(symbol, exchange, out_dir)
            if path is not None:
                paths.append(path)
        return paths

    @staticmethod
    def _bundle_has_content(bundle: StockNoteBundle) -> bool:
        if bundle.memo is not None and bundle.memo.body.strip():
            return True
        if any(entry.body.strip() for entry in bundle.entries):
            return True
        exchange = Exchange[bundle.exchange]
        return bool(reports_repo.list_reports(bundle.symbol, exchange, limit=1))

    def build_ai_snippet(
        self,
        bundle: StockNoteBundle,
        *,
        memo_max: int = 1500,
        entry_count: int = 5,
        entry_max: int = 200,
        report_count: int = 3,
        report_summary_max: int = 200,
    ) -> str:
        parts: list[str] = []
        memo_body = ""
        if bundle.memo is not None:
            memo_body = bundle.memo.body.strip()
        if memo_body:
            if len(memo_body) > memo_max:
                memo_body = memo_body[:memo_max] + "…"
            parts.append(f"【备忘】\n{memo_body}")

        lines: list[str] = []
        for entry in bundle.entries[: max(0, entry_count)]:
            body = entry.body.strip()
            if not body:
                continue
            if len(body) > entry_max:
                body = body[:entry_max] + "…"
            time_label = _format_entry_time(entry.created_at)
            lines.append(f"- {time_label}  {body}")
        if lines:
            parts.append("【最近流水】\n" + "\n".join(lines))

        reports_snippet = self._build_reports_snippet(
            bundle.symbol,
            Exchange[bundle.exchange],
            report_count=report_count,
            summary_max=report_summary_max,
        )
        if reports_snippet:
            parts.append(reports_snippet)
        return "\n\n".join(parts)

    def _build_reports_snippet(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        report_count: int = 3,
        summary_max: int = 200,
    ) -> str:
        reports = self.list_reports(symbol, exchange, limit=max(1, report_count))
        if not reports:
            return ""
        lines = [f"【分析报告】最近 {len(reports)} 篇摘要（全文请调 get_stock_analysis_report）"]
        for report in reports:
            summary = report.summary.strip() or report.title.strip()
            if len(summary) > summary_max:
                summary = summary[:summary_max] + "…"
            scope = f" · {report.source_scope}" if report.source_scope else ""
            lines.append(f"- #{report.id} {report.created_at}{scope}  {report.title}")
            if summary:
                lines.append(f"  {summary}")
        return "\n".join(lines)


def _report_from_row(row: dict[str, str | int]) -> StockAnalysisReport:
    return StockAnalysisReport(
        id=int(row["id"]),
        symbol=str(row["symbol"]),
        exchange=str(row["exchange"]),
        title=str(row["title"]),
        body=str(row["body"]),
        source_scope=str(row.get("source_scope") or ""),
        context_json=str(row.get("context_json") or ""),
        summary=str(row.get("summary") or ""),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def build_report_context_json(
    *,
    scope: str,
    summary: str,
    charts: list | None = None,
) -> str:
    payload: dict[str, object] = {"scope": scope.strip(), "summary": summary.strip()}
    if charts:
        payload["charts"] = [
            item.model_dump() if hasattr(item, "model_dump") else item for item in charts
        ]
    return json.dumps(payload, ensure_ascii=False)


def _format_entry_time(created_at: str) -> str:
    text = created_at.strip()
    if "T" in text:
        return text.split("T", 1)[1][:5]
    if " " in text:
        return text.split(" ", 1)[1][:5]
    return text[:5]
