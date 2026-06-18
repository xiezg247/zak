"""A 股极致短线·低吸（1 分 K + 14:30 后承接，T+1）。"""

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

from vnpy_ashare.trading.signals.pullback_intraday import (
    evaluate_pullback_intraday,
    resolve_daily_mas_for_date,
)

from .ashare_template import AShareTemplate


class AsharePullbackMinuteStrategy(AShareTemplate):
    """午后缩量回踩/承接买入；止损/跌破慢线/持仓到期卖出。"""

    author = "zak"

    ma_window: int = 5
    pullback_band_pct: float = 2.0
    min_dip_pct: float = -5.0
    max_dip_pct: float = -3.0
    window_start_minutes: int = 870
    window_end_minutes: int = 900
    stop_loss_pct: float = 0.05
    max_hold_days: int = 5
    trade_volume: int = 100

    entry_price: float = 0.0
    bars_held: int = 0

    parameters = [
        "ma_window",
        "pullback_band_pct",
        "min_dip_pct",
        "max_dip_pct",
        "window_start_minutes",
        "window_end_minutes",
        "stop_loss_pct",
        "max_hold_days",
        "trade_volume",
    ]
    variables = ["entry_price", "bars_held"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self._session_date: date | None = None
        self._session_bars: list[BarData] = []
        self._prev_close: float = 0.0
        self._daily_ma5: float = 0.0
        self._daily_ma10: float | None = None
        self._entry_attempted: bool = False

    def indicator_warmup_bars(self) -> int:
        return 240

    def on_init(self) -> None:
        self.write_log("A股极致短线·低吸（分 K）策略初始化")
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
        ma5, ma10, prev_close = resolve_daily_mas_for_date(
            self.vt_symbol,
            trading_day,
            ma_window=self.ma_window,
        )
        self._daily_ma5 = ma5 or 0.0
        self._daily_ma10 = ma10
        if prev_close > 0:
            self._prev_close = prev_close

    def _on_session_close(self, trading_day: date) -> None:
        if self.pos <= 0 or not self._session_bars:
            return
        last_bar = self._session_bars[-1]
        stop_hit = self.entry_price > 0 and last_bar.close_price <= self.entry_price * (1 - self.stop_loss_pct)
        below_ma = self._daily_ma10 is not None and last_bar.close_price < self._daily_ma10
        time_exit = self.bars_held >= self.max_hold_days
        if stop_hit or time_exit or below_ma:
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
            self._reset_session(trading_day)

        self._session_bars.append(bar)

        if self.pos > 0:
            if self.entry_price > 0 and bar.close_price <= self.entry_price * (1 - self.stop_loss_pct):
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.bars_held = 0
            return

        if self._entry_attempted or self._prev_close <= 0 or self._daily_ma5 <= 0:
            return

        snapshot = evaluate_pullback_intraday(
            self._session_bars,
            prev_close=self._prev_close,
            daily_ma5=self._daily_ma5,
            daily_ma10=self._daily_ma10,
            pullback_band_pct=self.pullback_band_pct,
            min_dip_pct=self.min_dip_pct,
            max_dip_pct=self.max_dip_pct,
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
