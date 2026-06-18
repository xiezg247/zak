"""A 股极致短线·半路（1 分 K + 9:40–10:30 窗口，T+1）。"""

from __future__ import annotations

from datetime import date

from vnpy.trader.constant import Interval
from vnpy_ctastrategy import (
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from vnpy_ashare.trading.signals.intraday_breakout_intraday import evaluate_intraday_breakout_intraday

from .ashare_template import AShareTemplate


class AshareIntradayBreakoutMinuteStrategy(AShareTemplate):
    """带量拉升半路买入；止损/止盈/持仓天数到期卖出。"""

    author = "zak"

    min_change_pct: float = 3.0
    max_change_pct: float = 7.0
    volume_ratio_min: float = 1.2
    window_start_minutes: int = 580
    window_end_minutes: int = 630
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.08
    max_hold_days: int = 3
    trade_volume: int = 100

    entry_price: float = 0.0
    bars_held: int = 0

    parameters = [
        "min_change_pct",
        "max_change_pct",
        "volume_ratio_min",
        "window_start_minutes",
        "window_end_minutes",
        "stop_loss_pct",
        "take_profit_pct",
        "max_hold_days",
        "trade_volume",
    ]
    variables = ["entry_price", "bars_held"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self._session_date: date | None = None
        self._session_bars: list[BarData] = []
        self._prev_close: float = 0.0
        self._entry_attempted: bool = False
        self._symbol_code: str = vt_symbol.split(".", 1)[0]

    def indicator_warmup_bars(self) -> int:
        return 240

    def on_init(self) -> None:
        self.write_log("A股极致短线·半路（分 K）策略初始化")
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

    def _reset_session(self, trading_day: date) -> None:
        self._session_date = trading_day
        self._session_bars = []
        self._entry_attempted = False

    def _on_session_close(self, trading_day: date) -> None:
        if self.pos <= 0 or not self._session_bars:
            return
        last_bar = self._session_bars[-1]
        stop_hit = self.entry_price > 0 and last_bar.close_price <= self.entry_price * (1 - self.stop_loss_pct)
        profit_hit = self.entry_price > 0 and last_bar.close_price >= self.entry_price * (1 + self.take_profit_pct)
        time_exit = self.bars_held >= self.max_hold_days
        if stop_hit or profit_hit or time_exit:
            self.sell_stock(last_bar.close_price, abs(self.pos) or self.trade_volume, trading_day)
            self.entry_price = 0.0
            self.bars_held = 0

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()
        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self._session_date != trading_day:
            if self._session_date is not None:
                self._on_session_close(self._session_date)
                if self.pos > 0:
                    self.bars_held += 1
                if self._session_bars:
                    self._prev_close = float(self._session_bars[-1].close_price)
            self._reset_session(trading_day)

        self._session_bars.append(bar)

        if self.pos > 0:
            if self.entry_price > 0 and bar.close_price <= self.entry_price * (1 - self.stop_loss_pct):
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.bars_held = 0
                return
            if self.entry_price > 0 and bar.close_price >= self.entry_price * (1 + self.take_profit_pct):
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.bars_held = 0
            return

        if self._entry_attempted or self._prev_close <= 0:
            return

        snapshot = evaluate_intraday_breakout_intraday(
            self._session_bars,
            prev_close=self._prev_close,
            symbol=self._symbol_code,
            min_change_pct=self.min_change_pct,
            max_change_pct=self.max_change_pct,
            volume_ratio_min=self.volume_ratio_min,
            window_start_minutes=self.window_start_minutes,
            window_end_minutes=self.window_end_minutes,
            phase="partial",
        )
        if not snapshot.eligible:
            return

        orders = self.buy_stock(snapshot.entry_price, volume)
        if orders:
            self.entry_price = snapshot.entry_price
            self.bars_held = 0
            self._entry_attempted = True

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
