"""交易体系 Playbook repository。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.domain.trading.playbook import PlaybookSection, PlaybookSectionUpdate
from vnpy_ashare.storage.connection import connect, init_app_db


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


def count_playbook_sections() -> int:
    init_app_db()
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM trading_playbook_sections").fetchone()
        return int(row["n"]) if row is not None else 0


def list_playbook_sections() -> tuple[PlaybookSection, ...]:
    init_app_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trading_playbook_sections ORDER BY sort_order, section_id",
        ).fetchall()
        return tuple(_row_to_section(row) for row in rows)


def upsert_playbook_sections(sections: tuple[PlaybookSection, ...]) -> None:
    if not sections:
        return
    init_app_db()
    now = _now_iso()
    with connect() as conn:
        for section in sections:
            conn.execute(
                """
                INSERT INTO trading_playbook_sections
                    (section_id, title, body_md, collapsed, sort_order, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(section_id) DO UPDATE SET
                    title = excluded.title,
                    body_md = excluded.body_md,
                    collapsed = excluded.collapsed,
                    sort_order = excluded.sort_order,
                    updated_at = excluded.updated_at
                """,
                (
                    section.section_id,
                    section.title,
                    section.body_md,
                    int(section.collapsed),
                    section.sort_order,
                    now,
                ),
            )


def update_playbook_section(section_id: str, patch: PlaybookSectionUpdate) -> None:
    init_app_db()
    now = _now_iso()
    with connect() as conn:
        row = conn.execute(
            "SELECT section_id FROM trading_playbook_sections WHERE section_id = ?",
            (section_id,),
        ).fetchone()
        if row is None:
            return
        if patch.collapsed is None:
            conn.execute(
                "UPDATE trading_playbook_sections SET body_md = ?, updated_at = ? WHERE section_id = ?",
                (patch.body_md, now, section_id),
            )
        else:
            conn.execute(
                """
                UPDATE trading_playbook_sections
                SET body_md = ?, collapsed = ?, updated_at = ?
                WHERE section_id = ?
                """,
                (patch.body_md, int(patch.collapsed), now, section_id),
            )


def set_playbook_section_collapsed(section_id: str, collapsed: bool) -> None:
    init_app_db()
    with connect() as conn:
        conn.execute(
            "UPDATE trading_playbook_sections SET collapsed = ?, updated_at = ? WHERE section_id = ?",
            (int(collapsed), _now_iso(), section_id),
        )
