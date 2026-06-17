"""选股结果行：行情基座 + 评分/标签扩展（Wave 2）。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ConfigDict, Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row

_SCORE_KEYS = frozenset(
    {
        "composite_score",
        "pattern_score",
        "leader_score",
        "seal_time_score",
        "resonance_score",
        "p_up",
        "score",
    }
)
_TAG_KEYS = frozenset(
    {
        "hit_reason",
        "pattern_hint",
        "diff_status",
        "flow_kind",
        "moneyflow_source",
        "signal",
        "signal_label",
        "industry",
        "concept",
        "source",
    }
)


class ScreenerResultRow(FrozenModel):
    """结构化选股结果：核心行情 + 配方评分 + 展示标签。"""

    model_config = ConfigDict(extra="forbid")

    quote: QuoteRow = Field(description="行情基座")
    scores: dict[str, float] = Field(default_factory=dict, description="数值型扩展列")
    tags: dict[str, str] = Field(default_factory=dict, description="文本型扩展列")

    def get(self, key: str, default: Any = None) -> Any:
        if key in type(self.quote).model_fields or key in (self.quote.__pydantic_extra__ or {}):
            value = self.quote.get(key, default)
            return value
        if key in self.scores:
            return self.scores[key]
        if key in self.tags:
            return self.tags[key]
        return default

    def to_dict(self) -> dict[str, Any]:
        payload = self.quote.to_dict()
        payload.update(self.scores)
        payload.update(self.tags)
        return payload

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ScreenerResultRow:
        raw = dict(data)
        scores: dict[str, float] = {}
        tags: dict[str, str] = {}
        quote_payload: dict[str, Any] = {}
        for key, value in raw.items():
            if key in _SCORE_KEYS and value is not None:
                try:
                    scores[key] = float(value)
                except (TypeError, ValueError):
                    quote_payload[key] = value
            elif key in _TAG_KEYS and value is not None:
                tags[key] = str(value)
            else:
                quote_payload[key] = value
        return cls(quote=coerce_quote_row(quote_payload), scores=scores, tags=tags)

    @classmethod
    def from_quote_row(cls, row: QuoteRow | Mapping[str, Any]) -> ScreenerResultRow:
        return cls.from_mapping(coerce_quote_row(row).to_dict())


def screener_rows_from_mappings(rows: list[Mapping[str, Any]]) -> list[ScreenerResultRow]:
    return [ScreenerResultRow.from_mapping(row) for row in rows]


def screener_rows_to_dicts(rows: list[ScreenerResultRow]) -> list[dict[str, Any]]:
    return [row.to_dict() for row in rows]
