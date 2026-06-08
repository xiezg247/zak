import numpy as np

from vnpy_ctastrategy import (
    ArrayManager,
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from .ashare_template import AShareTemplate


class AshareDoubleMaStrategy(AShareTemplate):
    """A 股双均线策略（仅做多、T+1、100股整数倍）"""

    author = "zak"

    fast_window: int = 10
    slow_window: int = 20
    trade_volume: int = 100

    fast_ma0: float = 0.0
    fast_ma1: float = 0.0
    slow_ma0: float = 0.0
    slow_ma1: float = 0.0

    parameters = ["fast_window", "slow_window", "trade_volume"]
    variables = ["fast_ma0", "fast_ma1", "slow_ma0", "slow_ma1"]

    def on_init(self) -> None:
        self.write_log("A股双均线策略初始化")
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()
        self.load_bar(max(self.fast_window, self.slow_window) + 5)

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
        if not am.inited:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 <= self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if cross_over:
            self.buy_stock(bar.close_price, volume)
        elif cross_below:
            self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
