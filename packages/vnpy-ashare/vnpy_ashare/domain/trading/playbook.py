"""交易体系 Playbook 领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel, MutableModel

PLAYBOOK_SECTION_IDS: tuple[str, ...] = (
    "timing",
    "universe",
    "execution",
    "risk",
    "discipline",
)


class PlaybookSection(FrozenModel):
    section_id: str = Field(description="章节标识")
    title: str = Field(description="章节标题")
    body_md: str = Field(description="Markdown 正文")
    collapsed: bool = Field(default=False, description="是否折叠")
    sort_order: int = Field(description="排序")


class PlaybookSectionUpdate(MutableModel):
    body_md: str = Field(description="Markdown 正文")
    collapsed: bool | None = Field(default=None, description="是否折叠")


class HomePlaybookStatus(FrozenModel):
    profile_title: str = Field(description="策略 Profile 标题")
    phase_label: str = Field(description="市场阶段标签")
    emotion_label: str = Field(description="情绪周期")
    emotion_position_hint: str = Field(description="情绪建议仓位")
    risk_label: str = Field(description="风控闸状态")
    allow_new_positions: bool = Field(description="是否可新开仓")
    daily_pnl_text: str = Field(description="当日盈亏")
    plan_text: str = Field(description="今日计划摘要")
    position_text: str = Field(description="持仓摘要")
    discipline_progress: str = Field(default="", description="纪律 checklist 进度")
    off_plan_symbols: tuple[str, ...] = Field(default=(), description="计划外持仓 vt_symbol")
    alert: str = Field(default="", description="顶栏警示文案")


class DisciplineCheckItem(FrozenModel):
    check_id: str = Field(description="检查项标识")
    label: str = Field(description="展示文案")
    checked: bool = Field(default=False, description="是否已勾选")
