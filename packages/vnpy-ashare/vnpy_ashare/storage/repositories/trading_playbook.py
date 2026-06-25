"""交易体系 Playbook repository。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from vnpy_ashare.domain.trading.playbook import PlaybookSection, PlaybookSectionUpdate
from vnpy_ashare.storage.repository.app import AppBaseRepository
from vnpy_common.storage.tables import trading_playbook_sections as tps


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row_to_section(row) -> PlaybookSection:
    return PlaybookSection(
        section_id=str(row["section_id"]),
        title=str(row["title"]),
        body_md=str(row["body_md"] or ""),
        collapsed=bool(row["collapsed"]),
        sort_order=int(row["sort_order"]),
    )


class PlaybookRepository(AppBaseRepository):
    table = tps

    def count_sections(self) -> int:
        row = self.fetchone(select(func.count()).select_from(tps))
        return int(row[0]) if row else 0

    def list_sections(self) -> tuple[PlaybookSection, ...]:
        rows = self.fetchall(
            select(tps).order_by(tps.c.sort_order, tps.c.section_id)
        )
        return tuple(_row_to_section(row) for row in rows)

    def upsert_sections(self, sections: tuple[PlaybookSection, ...]) -> None:
        if not sections:
            return
        now = _now_iso()

        def _write(conn) -> None:
            for section in sections:
                stmt = pg_insert(tps).values(
                    section_id=section.section_id,
                    title=section.title,
                    body_md=section.body_md,
                    collapsed=int(section.collapsed),
                    sort_order=section.sort_order,
                    updated_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[tps.c.section_id],
                    set_={
                        "title": stmt.excluded.title,
                        "body_md": stmt.excluded.body_md,
                        "collapsed": stmt.excluded.collapsed,
                        "sort_order": stmt.excluded.sort_order,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                conn.execute_stmt(stmt)

        self.run(_write)

    def update_section(self, section_id: str, patch: PlaybookSectionUpdate) -> None:
        if not self.exists_where(tps.c.section_id == section_id):
            return
        now = _now_iso()
        if patch.collapsed is None:
            self.update_matching({"body_md": patch.body_md, "updated_at": now}, tps.c.section_id == section_id)
        else:
            self.update_matching(
                {"body_md": patch.body_md, "collapsed": int(patch.collapsed), "updated_at": now},
                tps.c.section_id == section_id,
            )

    def set_collapsed(self, section_id: str, collapsed: bool) -> None:
        self.update_matching(
            {"collapsed": int(collapsed), "updated_at": _now_iso()},
            tps.c.section_id == section_id,
        )


_repo = PlaybookRepository()


def count_playbook_sections() -> int:
    return _repo.count_sections()


def list_playbook_sections() -> tuple[PlaybookSection, ...]:
    return _repo.list_sections()


def upsert_playbook_sections(sections: tuple[PlaybookSection, ...]) -> None:
    _repo.upsert_sections(sections)


def update_playbook_section(section_id: str, patch: PlaybookSectionUpdate) -> None:
    _repo.update_section(section_id, patch)


def set_playbook_section_collapsed(section_id: str, collapsed: bool) -> None:
    _repo.set_collapsed(section_id, collapsed)
