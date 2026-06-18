"""A 股极致短线·打板（1 分 K + 触板规则，T+1）。"""

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

from strategies.ultra_short_signals import classify_limit_board_signal

from vnpy_ashare.trading.signals.limit_board_intraday import evaluate_limit_board_intraday

from .ashare_template import AShareTemplate


class AshareLimitBoardMinuteStrategy(AShareTemplate):
    """分 K 首次触板买入；隔日或止损/持仓天数到期卖出。"""

    author = "zak"

    fast_window: int = 5
    slow_window: int = 10
    max_hold_days: int = 2
    stop_loss_pct: float = 0.05
    reject_one_word: bool = True
    one_word_amplitude_max: float = 0.5
    seal_cutoff_minutes: int = 630
    reject_broken: bool = True
    trade_volume: int = 100

    entry_price: float = 0.0
    bars_held: int = 0

    parameters = [
        "fast_window",
        "slow_window",
        "max_hold_days",
        "stop_loss_pct",
        "reject_one_word",
        "one_word_amplitude_max",
        "seal_cutoff_minutes",
        "reject_broken",
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
        self.write_log("A股极致短线·打板（分 K）策略初始化")
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
        if self.pos <= 0:
            return
        limit_up = False
        if self._session_bars and self._prev_close > 0:
            snapshot = evaluate_limit_board_intraday(
                self._session_bars,
                prev_close=self._prev_close,
                symbol=self._symbol_code,
                reject_one_word=self.reject_one_word,
                one_word_amplitude_max=self.one_word_amplitude_max,
                cutoff_minutes=self.seal_cutoff_minutes,
                reject_broken=False,
                phase="closed",
            )
            limit_up = snapshot.seal_reopen_kind != "broken" and bool(snapshot.first_time)
        signal = classify_limit_board_signal(
            limit_up_today=limit_up,
            recent_days=1,
            days_since_event=0 if limit_up else 1,
        )
        stop_hit = False
        if self._session_bars and self.entry_price > 0:
            last_close = float(self._session_bars[-1].close_price)
            stop_hit = last_close <= self.entry_price * (1 - self.stop_loss_pct)
        time_exit = self.bars_held >= self.max_hold_days
        if stop_hit or time_exit or signal != "buy":
            last_bar = self._session_bars[-1]
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

        if self._entry_attempted or self._prev_close <= 0:
            return

        snapshot = evaluate_limit_board_intraday(
            self._session_bars,
            prev_close=self._prev_close,
            symbol=self._symbol_code,
            reject_one_word=self.reject_one_word,
            one_word_amplitude_max=self.one_word_amplitude_max,
            cutoff_minutes=self.seal_cutoff_minutes,
            reject_broken=self.reject_broken,
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
