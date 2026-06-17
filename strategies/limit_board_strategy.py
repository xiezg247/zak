"""A 股极致短线·打板（日 K + 封板时间代理，T+1）。"""

from __future__ import annotations

from vnpy_ctastrategy import (
    ArrayManager,
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from strategies.ultra_short_signals import (
    _limit_up_bar,
    classify_limit_board_signal,
)

from .ashare_template import AShareTemplate


class AshareLimitBoardStrategy(AShareTemplate):
    """涨停封板日买入；隔日或止损/持仓天数到期卖出。"""

    author = "zak"

    fast_window: int = 5
    slow_window: int = 10
    max_hold_days: int = 2
    stop_loss_pct: float = 0.05
    reject_one_word: bool = True
    one_word_amplitude_max: float = 0.5
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
        "trade_volume",
    ]
    variables = ["entry_price", "bars_held"]

    def indicator_warmup_bars(self) -> int:
        return max(self.slow_window, 3) + 5

    def on_init(self) -> None:
        self.write_log("A股极致短线·打板策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = self.init_array_manager()
        self.load_indicator_bars()

    def on_start(self) -> None:
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self) -> None:
        self.write_log("策略停止")
        self.put_event()

    def on_tick(self, tick: TickData) -> None:
        self.bg.update_tick(tick)

    @staticmethod
    def _is_one_word_bar(am: ArrayManager, *, max_amplitude: float) -> bool:
        if am.count < 1:
            return False
        high = float(am.high[-1])
        low = float(am.low[-1])
        close = float(am.close[-1])
        if close <= 0:
            return False
        amplitude = (high - low) / close * 100
        return amplitude >= 0 and amplitude < max_amplitude

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if am.count < 3:
            return

        closes = [float(value) for value in am.close]
        highs = [float(value) for value in am.high]
        dates = [bar.datetime.date()] * am.count
        symbol = bar.vt_symbol.split(".", 1)[0]
        last_index = am.count - 1
        limit_up = _limit_up_bar(closes, highs, dates, last_index, symbol=symbol)
        one_word = self._is_one_word_bar(am, max_amplitude=self.one_word_amplitude_max)

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            self.bars_held += 1
            stop_hit = self.entry_price > 0 and bar.close_price <= self.entry_price * (1 - self.stop_loss_pct)
            time_exit = self.bars_held >= self.max_hold_days
            signal = classify_limit_board_signal(
                limit_up_today=limit_up,
                recent_days=1,
                days_since_event=0 if limit_up else 1,
            )
            if stop_hit or time_exit or signal != "buy":
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.bars_held = 0
        elif limit_up and not (self.reject_one_word and one_word):
            orders = self.buy_stock(bar.close_price, volume)
            if orders:
                self.entry_price = bar.close_price
                self.bars_held = 0

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
