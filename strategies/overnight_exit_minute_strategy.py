"""A 股隔日退出规则（1 分 K 回测 · 日末建仓 + 次日分 K 退出）。"""

from __future__ import annotations

from datetime import date, time

from vnpy.trader.constant import Interval
from vnpy_ctastrategy import (
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.trading.exit.overnight_exit_intraday import evaluate_overnight_exit_intraday

from .ashare_template import AShareTemplate


class AshareOvernightExitMinuteStrategy(AShareTemplate):
    """验证隔日退出：当日最后一根 1m 买入，次日起按分 K 规则卖出。"""

    author = "zak"

    stop_loss_pct: float = 0.05
    stop_minutes: int = 30
    max_hold_days: int = 2
    trade_volume: int = 100
    entry_at_session_close: bool = True

    entry_price: float = 0.0
    entry_date: str = ""
    bars_held: int = 0

    parameters = [
        "stop_loss_pct",
        "stop_minutes",
        "max_hold_days",
        "trade_volume",
        "entry_at_session_close",
    ]
    variables = ["entry_price", "entry_date", "bars_held"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self._session_date: date | None = None
        self._session_bars: list[BarData] = []
        self._prev_close: float = 0.0
        self._pending_session_close_entry: bool = False

    def indicator_warmup_bars(self) -> int:
        return 240

    def on_init(self) -> None:
        self.write_log("A股隔日退出（分 K）回测策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.load_indicator_bars(interval=Interval.MINUTE)

    def on_start(self) -> None:
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self) -> None:
        self.write_log("策略停止")
        self.put_event()

    def on_tick(self, tick: TickData) -> None:
        self.bg.update_tick(tick)

    def _position_record(self) -> PositionRecord:
        return PositionRecord(
            symbol=self.vt_symbol.split(".", 1)[0],
            exchange=self.vt_symbol.split(".", 1)[1],
            name="",
            cost_price=self.entry_price,
            volume=self.trade_volume,
            buy_date=self.entry_date or (self._session_date.isoformat() if self._session_date else ""),
        )

    def _reset_session(self, trading_day: date) -> None:
        self._session_date = trading_day
        self._session_bars = []
        self._pending_session_close_entry = False

    def _try_session_close_entry(self, bar: BarData, trading_day: date) -> None:
        if not self.entry_at_session_close or self.pos > 0:
            return
        local = bar.datetime
        if local.time() < time(14, 55):
            return
        volume = self.round_volume(self.trade_volume)
        orders = self.buy_stock(bar.close_price, volume)
        if orders:
            self.entry_price = bar.close_price
            self.entry_date = trading_day.isoformat()
            self.bars_held = 0
            self.last_buy_date = trading_day

    def _on_session_close(self, trading_day: date) -> None:
        if self.pos > 0:
            self.bars_held += 1
            if self.bars_held >= self.max_hold_days and self._session_bars:
                last = self._session_bars[-1]
                self.sell_stock(last.close_price, abs(self.pos) or self.trade_volume, trading_day)
                self.entry_price = 0.0
                self.entry_date = ""
                self.bars_held = 0

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()
        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self._session_date != trading_day:
            if self._session_date is not None:
                self._on_session_close(self._session_date)
                if self._session_bars:
                    self._prev_close = float(self._session_bars[-1].close_price)
            self._reset_session(trading_day)

        self._session_bars.append(bar)

        if self.pos > 0 and self.last_buy_date is not None and trading_day > self.last_buy_date:
            snapshot = evaluate_overnight_exit_intraday(
                self._session_bars,
                self._position_record(),
                prev_close=self._prev_close,
                stop_loss_pct=self.stop_loss_pct,
                stop_minutes=self.stop_minutes,
                phase="partial",
            )
            if snapshot.signal == "sell":
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.entry_date = ""
                self.bars_held = 0
                self.put_event()
                return

        if self.pos <= 0:
            self._try_session_close_entry(bar, trading_day)

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
