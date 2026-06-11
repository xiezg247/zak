from vnpy_ctastrategy import (
    ArrayManager,
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from .ashare_template import AShareTemplate


class AshareShortBreakoutStrategy(AShareTemplate):
    """A 股短线放量突破（5 日高点 + 量比 + 快均线确认，仅做多、T+1）"""

    author = "zak"

    fast_window: int = 5
    slow_window: int = 10
    breakout_lookback: int = 5
    volume_ratio_min: float = 1.5
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.06
    max_hold_days: int = 3
    trade_volume: int = 100

    fast_ma0: float = 0.0
    fast_ma1: float = 0.0
    slow_ma0: float = 0.0
    slow_ma1: float = 0.0
    entry_price: float = 0.0
    bars_held: int = 0

    parameters = [
        "fast_window",
        "slow_window",
        "breakout_lookback",
        "volume_ratio_min",
        "stop_loss_pct",
        "take_profit_pct",
        "max_hold_days",
        "trade_volume",
    ]
    variables = [
        "fast_ma0",
        "fast_ma1",
        "slow_ma0",
        "slow_ma1",
        "entry_price",
        "bars_held",
    ]

    def on_init(self) -> None:
        self.write_log("A股短线放量突破策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()
        warmup = max(self.slow_window, self.breakout_lookback) + 10
        self.load_bar(warmup)

    def on_start(self) -> None:
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self) -> None:
        self.write_log("策略停止")
        self.put_event()

    def on_tick(self, tick: TickData) -> None:
        self.bg.update_tick(tick)

    @staticmethod
    def _volume_ratio(am: ArrayManager, window: int = 5) -> float:
        if am.count < window * 2:
            return 0.0
        recent = am.volume[-window:]
        base = am.volume[-window * 2 : -window]
        avg_recent = float(recent.sum()) / len(recent)
        avg_base = float(base.sum()) / len(base)
        if avg_base <= 0:
            return 0.0
        return avg_recent / avg_base

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        min_bars = max(self.slow_window, self.breakout_lookback) + 2
        if am.count < min_bars:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]

        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1
        volume_ratio = self._volume_ratio(am)
        prior_highs = am.high[-(self.breakout_lookback + 1) : -1]
        breakout_level = float(prior_highs.max()) if len(prior_highs) else 0.0

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            self.bars_held += 1
            stop_hit = (
                self.entry_price > 0
                and bar.close_price <= self.entry_price * (1 - self.stop_loss_pct)
            )
            profit_hit = (
                self.entry_price > 0
                and bar.close_price >= self.entry_price * (1 + self.take_profit_pct)
            )
            time_exit = self.bars_held >= self.max_hold_days
            if cross_below or stop_hit or profit_hit or time_exit:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.bars_held = 0
        elif (
            breakout_level > 0
            and bar.close_price > breakout_level
            and volume_ratio >= self.volume_ratio_min
            and self.fast_ma0 > self.slow_ma0
        ):
            orders = self.buy_stock(bar.close_price, volume)
            if orders:
                self.entry_price = bar.close_price
                self.bars_held = 0

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
