"""雷达卡片行与共振领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_common.domain.base import FrozenModel


class RadarRow(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(description="证券名称")
    symbol: str = Field(description="证券代码")
    price: float | None = Field(description="最新价")
    change_pct: float | None = Field(description="涨跌幅（%）")
    metric_label: str = Field(description="主指标标签")
    metric_value: str = Field(description="主指标值")
    sub_label: str = Field(description="副指标标签")
    sub_value: str = Field(description="副指标值")
    leader_score: float | None = Field(default=None, description="龙头评分")
    leader_tier: str = Field(default="", description="龙头分层（龙一/龙二/跟风）")
    limit_times: float | None = Field(default=None, description="连板数")


class RadarCardData(FrozenModel):
    card_id: str = Field(description="卡片唯一标识")
    title: str = Field(description="卡片标题")
    subtitle: str = Field(description="卡片副标题")
    rows: tuple[RadarRow, ...] = Field(description="卡片行数据")
    empty_message: str = Field(description="无数据时的提示文案")
    updated_at: str = Field(description="数据更新时间")
    run_id: str = Field(default="", description="选股任务运行 ID")
    detail_page_key: str = Field(default="", description="详情页跳转键")
    total_count: int = Field(default=0, description="符合条件的标的总数")
    ai_hint: str = Field(default="", description="AI 分析提示语")
    sector_names: tuple[str, ...] = Field(default=(), description="关联板块名称")


class RadarResonanceEntry(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(description="证券名称")
    symbol: str = Field(description="证券代码")
    card_count: int = Field(description="共振卡片数量")
    card_titles: tuple[str, ...] = Field(description="共振卡片标题列表")
    price: float | None = Field(description="最新价")
    change_pct: float | None = Field(description="涨跌幅（%）")
    resonance_score: float = Field(default=0.0, description="共振得分")
