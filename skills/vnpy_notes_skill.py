"""个股笔记 Skill。"""

from __future__ import annotations

import json

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_skills.domain import SkillTemplate, ToolSpec


class VnpyNotesSkill(SkillTemplate):
    skill_name = "vnpy-notes"
    author = "zak"
    description = "查看与管理个股投研笔记（备忘 + 流水 + 分析报告）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_stock_notes",
                description="获取指定标的投研笔记：长文备忘与最近流水条目",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "股票代码，如 600519.SSE",
                        },
                        "entry_limit": {
                            "type": "integer",
                            "description": "流水条数上限，默认 20",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="append_stock_note_entry",
                description="为标的追加一条流水笔记（盘中观察、碎片记录）",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SSE"},
                        "body": {"type": "string", "description": "流水正文"},
                    },
                    "required": ["symbol", "body"],
                },
            ),
            ToolSpec(
                name="update_stock_note_memo",
                description="更新标的备忘长文（全量替换正文）",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SSE"},
                        "body": {"type": "string", "description": "备忘全文"},
                    },
                    "required": ["symbol", "body"],
                },
            ),
            ToolSpec(
                name="delete_stock_note_entry",
                description="删除一条流水笔记（按 entry_id）",
                parameters={
                    "type": "object",
                    "properties": {
                        "entry_id": {"type": "integer", "description": "流水记录 id"},
                    },
                    "required": ["entry_id"],
                },
            ),
            ToolSpec(
                name="clear_stock_notes",
                description="清空指定标的的全部备忘与流水",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SSE"},
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="list_stock_analysis_reports",
                description="列出指定标的的历史分析报告（标题与摘要，不含全文）",
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "股票代码，如 600519.SSE"},
                        "limit": {
                            "type": "integer",
                            "description": "返回条数上限，默认 20",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            ToolSpec(
                name="get_stock_analysis_report",
                description="按 report_id 获取分析报告全文（Markdown）",
                parameters={
                    "type": "object",
                    "properties": {
                        "report_id": {"type": "integer", "description": "报告 id"},
                    },
                    "required": ["report_id"],
                },
            ),
        ]

    def _get_note_service(self):
        svc = self._services.get("note")
        if svc is None:
            raise RuntimeError("NoteService 未就绪")
        return svc

    def _parse_symbol(self, symbol: str) -> tuple[str, object, str] | str:
        item = parse_stock_symbol(symbol)
        if item is None:
            return json.dumps(
                {"error": f"无法解析代码: {symbol}，请使用 600519.SSE 格式"},
                ensure_ascii=False,
            )
        return item.symbol, item.exchange, item.vt_symbol

    def get_stock_notes(self, symbol: str, entry_limit: int = 20) -> str:
        parsed = self._parse_symbol(symbol)
        if isinstance(parsed, str):
            return parsed
        sym, exchange, vt = parsed
        svc = self._get_note_service()
        bundle = svc.get_bundle(sym, exchange, entry_limit=max(1, min(int(entry_limit), 50)))
        memo = None
        if bundle.memo is not None and bundle.memo.body.strip():
            memo = {
                "body": bundle.memo.body,
                "updated_at": bundle.memo.updated_at,
            }
        entries = [
            {
                "id": entry.id,
                "body": entry.body,
                "created_at": entry.created_at,
            }
            for entry in bundle.entries
        ]
        reports = svc.list_reports(sym, exchange, limit=5)
        report_items = [
            {
                "id": report.id,
                "title": report.title,
                "summary": report.summary,
                "source_scope": report.source_scope,
                "created_at": report.created_at,
            }
            for report in reports
        ]
        return json.dumps(
            {
                "vt_symbol": vt,
                "memo": memo,
                "entries": entries,
                "entry_count": len(entries),
                "reports": report_items,
                "report_count": len(report_items),
            },
            ensure_ascii=False,
        )

    def append_stock_note_entry(self, symbol: str, body: str) -> str:
        parsed = self._parse_symbol(symbol)
        if isinstance(parsed, str):
            return parsed
        sym, exchange, vt = parsed
        entry = self._get_note_service().append_entry(sym, exchange, body)
        if entry is None:
            return json.dumps(
                {"success": False, "vt_symbol": vt, "message": "流水正文为空"},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "success": True,
                "vt_symbol": vt,
                "entry": {
                    "id": entry.id,
                    "body": entry.body,
                    "created_at": entry.created_at,
                },
            },
            ensure_ascii=False,
        )

    def update_stock_note_memo(self, symbol: str, body: str) -> str:
        parsed = self._parse_symbol(symbol)
        if isinstance(parsed, str):
            return parsed
        sym, exchange, vt = parsed
        self._get_note_service().upsert_memo(sym, exchange, body)
        return json.dumps(
            {"success": True, "vt_symbol": vt, "message": "备忘已更新"},
            ensure_ascii=False,
        )

    def delete_stock_note_entry(self, entry_id: int) -> str:
        ok = self._get_note_service().delete_entry(int(entry_id))
        return json.dumps(
            {
                "success": ok,
                "entry_id": int(entry_id),
                "message": "已删除" if ok else "记录不存在",
            },
            ensure_ascii=False,
        )

    def clear_stock_notes(self, symbol: str) -> str:
        parsed = self._parse_symbol(symbol)
        if isinstance(parsed, str):
            return parsed
        sym, exchange, vt = parsed
        cleared = self._get_note_service().clear_notes(sym, exchange)
        return json.dumps(
            {
                "success": True,
                "vt_symbol": vt,
                "cleared": cleared,
            },
            ensure_ascii=False,
        )

    def list_stock_analysis_reports(self, symbol: str, limit: int = 20) -> str:
        parsed = self._parse_symbol(symbol)
        if isinstance(parsed, str):
            return parsed
        sym, exchange, vt = parsed
        svc = self._get_note_service()
        reports = svc.list_reports(sym, exchange, limit=max(1, min(int(limit), 100)))
        items = [
            {
                "id": report.id,
                "title": report.title,
                "summary": report.summary,
                "source_scope": report.source_scope,
                "created_at": report.created_at,
            }
            for report in reports
        ]
        return json.dumps(
            {
                "vt_symbol": vt,
                "reports": items,
                "count": len(items),
            },
            ensure_ascii=False,
        )

    def get_stock_analysis_report(self, report_id: int) -> str:
        report = self._get_note_service().get_report(int(report_id))
        if report is None:
            return json.dumps(
                {"error": f"报告不存在: id={report_id}"},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "id": report.id,
                "vt_symbol": report.vt_symbol,
                "title": report.title,
                "body": report.body,
                "source_scope": report.source_scope,
                "context_json": report.context_json,
                "summary": report.summary,
                "created_at": report.created_at,
                "updated_at": report.updated_at,
            },
            ensure_ascii=False,
        )
