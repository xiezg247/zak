from vnpy_ctastrategy import (
    ArrayManager,
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from .ashare_template import AShareTemplate


class AshareTrendMaStrategy(AShareTemplate):
    """A 股趋势双均线 + ADX 过滤 + 追踪止损（仅做多、T+1）"""

    author = "zak"

    fast_window: int = 20
    slow_window: int = 60
    adx_period: int = 14
    adx_threshold: float = 25.0
    trailing_stop_pct: float = 0.12
    trade_volume: int = 100

    fast_ma0: float = 0.0
    fast_ma1: float = 0.0
    slow_ma0: float = 0.0
    slow_ma1: float = 0.0
    adx_value: float = 0.0
    highest_since_entry: float = 0.0
    entry_price: float = 0.0

    parameters = [
        "fast_window",
        "slow_window",
        "adx_period",
        "adx_threshold",
        "trailing_stop_pct",
        "trade_volume",
    ]
    variables = [
        "fast_ma0",
        "fast_ma1",
        "slow_ma0",
        "slow_ma1",
        "adx_value",
        "highest_since_entry",
        "entry_price",
    ]

    def indicator_warmup_bars(self) -> int:
        return max(self.slow_window, self.adx_period * 3) + 10

    def on_init(self) -> None:
        self.write_log("A股趋势均线策略初始化")
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

    def on_bar(self, bar: BarData) -> None:
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        min_bars = max(self.slow_window, self.adx_period * 2) + 2
        if am.count < min_bars:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]

        self.adx_value = float(am.adx(self.adx_period))

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 <= self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            self.highest_since_entry = max(self.highest_since_entry, bar.close_price)
            trail_stop = self.highest_since_entry * (1 - self.trailing_stop_pct)
            structure_break = bar.close_price < self.slow_ma0
            if cross_below or structure_break or bar.close_price < trail_stop:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.highest_since_entry = 0.0
        elif (
            cross_over
            and self.adx_value >= self.adx_threshold
            and bar.close_price > self.slow_ma0
            and self.slow_ma0 >= self.slow_ma1
        ):
            orders = self.buy_stock(bar.close_price, volume)
            if orders:
                self.entry_price = bar.close_price
                self.highest_since_entry = bar.close_price

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
