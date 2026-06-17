"""全市场统一行情行（表格 / 选股 / 雷达 / 信号共用）。"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.symbols import StockItem


class QuoteRow(MutableModel):
    """行情行载体；选股/雷达管道可通过 extra 或 __setitem__ 附加动态列。"""

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
    )

    symbol: str = Field(default="", description="六位股票代码")
    name: str = Field(default="", description="证券名称")
    vt_symbol: str = Field(default="", description="VeighNa 合约代码")
    exchange: str = Field(default="", description="交易所代码")
    last_price: float = Field(default=0.0, description="最新价")
    prev_close: float = Field(default=0.0, description="昨收价")
    open_price: float = Field(default=0.0, description="开盘价")
    high_price: float = Field(default=0.0, description="最高价")
    low_price: float = Field(default=0.0, description="最低价")
    change_pct: float = Field(default=0.0, description="涨跌幅（%）")
    change_amount: float = Field(default=0.0, description="涨跌额")
    turnover_rate: float = Field(default=0.0, description="换手率（%）")
    volume: float = Field(default=0.0, description="成交量")
    amount: float = Field(default=0.0, description="成交额")
    volume_ratio: float = Field(default=0.0, description="量比")
    net_mf_amount: float = Field(default=0.0, description="主力净流入（万元）")
    limit_times: float = Field(default=0.0, description="连板数")
    change_speed_5m: float = Field(default=0.0, description="5 分钟涨速（%）")
    amplitude: float = Field(default=0.0, description="振幅（%）")
    close: float = Field(default=0.0, description="收盘价（常与 last_price 相同）")
    first_time: str | None = Field(default=None, description="首次触板时间")
    seal_time_score: float | None = Field(default=None, description="封板时间得分")

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        payload = dict(data)
        vt_symbol = str(payload.get("vt_symbol") or "").strip()
        if not str(payload.get("symbol") or "").strip() and vt_symbol:
            payload["symbol"] = vt_symbol.split(".")[0]
        return payload

    def to_dict(self) -> dict[str, Any]:
        """含 extra 字段的 plain dict。"""
        return self.model_dump(mode="python")

    def get(self, key: str, default: Any = None) -> Any:
        if key in type(self).model_fields:
            value = getattr(self, key)
            return default if value is None and default is not None else value
        extra = self.__pydantic_extra__ or {}
        return extra.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key in type(self).model_fields:
            return getattr(self, key)
        extra = self.__pydantic_extra__ or {}
        if key in extra:
            return extra[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __delitem__(self, key: str) -> None:
        if key in type(self).model_fields:
            raise TypeError(f"无法删除声明字段: {key}")
        extra = self.__pydantic_extra__
        if extra is None or key not in extra:
            raise KeyError(key)
        del extra[key]

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def keys(self) -> set[str]:
        return set(self.to_dict().keys())


def quote_row_from_stock_and_snapshot(item: StockItem, quote: QuoteSnapshot) -> QuoteRow:
    """由 StockItem + QuoteSnapshot 构建行情行。"""
    return QuoteRow(
        symbol=item.symbol,
        name=quote.name or item.name,
        vt_symbol=item.vt_symbol,
        exchange=item.exchange.value,
        last_price=quote.last_price,
        prev_close=quote.prev_close,
        open_price=quote.open_price,
        high_price=quote.high_price,
        low_price=quote.low_price,
        change_pct=quote.change_pct,
        change_amount=quote.change_amount,
        turnover_rate=quote.turnover_rate,
        volume=quote.volume,
        amount=quote.amount,
        volume_ratio=quote.volume_ratio,
        net_mf_amount=quote.net_mf_amount,
        limit_times=quote.limit_times,
        change_speed_5m=quote.change_speed_5m,
        amplitude=quote.amplitude,
        close=quote.last_price,
    )


def quote_row_from_mapping(data: Mapping[str, Any]) -> QuoteRow:
    """从 plain dict 构造（忽略未知键由 extra 接收）。"""
    return QuoteRow.model_validate(dict(data))


def coerce_quote_row(row: QuoteRow | Mapping[str, Any]) -> QuoteRow:
    if isinstance(row, QuoteRow):
        return row
    return quote_row_from_mapping(row)


def coerce_quote_rows(rows: Sequence[QuoteRow | Mapping[str, Any]]) -> list[QuoteRow]:
    return [coerce_quote_row(row) for row in rows]


def quote_rows_by_vt(rows: Sequence[QuoteRow | Mapping[str, Any]] | None = None) -> dict[str, QuoteRow]:
    source = coerce_quote_rows(rows) if rows is not None else []
    return {row.vt_symbol.strip(): row for row in source if row.vt_symbol.strip()}
