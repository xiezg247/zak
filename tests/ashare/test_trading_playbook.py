"""Playbook 服务测试。"""

from __future__ import annotations

from vnpy_ashare.config.playbook_templates.defaults import playbook_template_sections
from vnpy_ashare.domain.trading.playbook import PLAYBOOK_SECTION_IDS
from vnpy_ashare.services.trading_playbook import (
    apply_playbook_template_merge,
    build_home_playbook_status,
    build_mirror_appendix,
    ensure_playbook_seeded,
    list_playbook_merge_candidate_sections,
    load_playbook_sections,
    render_section_markdown,
)
from vnpy_ashare.storage.repositories.trading_playbook import count_playbook_sections, update_playbook_section
from vnpy_ashare.domain.trading.playbook import PlaybookSectionUpdate


def test_playbook_template_has_five_sections() -> None:
    sections = playbook_template_sections("ultra_short")
    assert len(sections) == 5
    assert [item.section_id for item in sections] == list(PLAYBOOK_SECTION_IDS)


def test_playbook_seed_and_render(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "zak.db"
    monkeypatch.setattr("vnpy_ashare.storage.connection.get_app_db_path", lambda: db_path)

    assert count_playbook_sections() == 0
    ensure_playbook_seeded()
    sections = load_playbook_sections()
    assert len(sections) == 5

    universe = next(item for item in sections if item.section_id == "universe")
    rendered = render_section_markdown(universe)
    assert "当前配置镜像" in rendered
    assert "Profile" in build_mirror_appendix("universe")


def test_build_home_status_without_engine() -> None:
    status = build_home_playbook_status(None)
    assert status.profile_title
    assert status.phase_label


def test_playbook_merge_candidates_respect_user_edits(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "zak.db"
    monkeypatch.setattr("vnpy_ashare.storage.connection.get_app_db_path", lambda: db_path)

    ensure_playbook_seeded()
    update_playbook_section("timing", PlaybookSectionUpdate(body_md="我的自定义择时规则"))

    candidates = list_playbook_merge_candidate_sections("short_swing", "ultra_short")
    assert "timing" not in candidates
    assert "execution" in candidates

    apply_playbook_template_merge("ultra_short", ("execution",))
    execution = next(item for item in load_playbook_sections() if item.section_id == "execution")
    ultra_tpl = next(
        item for item in playbook_template_sections("ultra_short") if item.section_id == "execution"
    )
    assert execution.body_md.strip() == ultra_tpl.body_md.strip()
