"""A 股极致短线·低吸（日 K MA5 缩量回踩，T+1）。"""

from __future__ import annotations

from vnpy_ctastrategy import (
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from strategies.ultra_short_signals import classify_pullback_bar

from .ashare_template import AShareTemplate


class AsharePullbackStrategy(AShareTemplate):
    """回踩 MA5 缩量买入；跌破慢线/止损/持仓到期卖出。"""

    author = "zak"

    fast_window: int = 5
    slow_window: int = 10
    ma_window: int = 5
    pullback_band_pct: float = 2.0
    stop_loss_pct: float = 0.05
    max_hold_days: int = 5
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
        "ma_window",
        "pullback_band_pct",
        "stop_loss_pct",
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

    def indicator_warmup_bars(self) -> int:
        return max(self.slow_window, self.ma_window) + 5

    def on_init(self) -> None:
        self.write_log("A股极致短线·低吸策略初始化")
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
        min_bars = max(self.slow_window, self.ma_window) + 2
        if am.count < min_bars:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]
        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1

        closes = [float(value) for value in am.close]
        volumes = [float(value) for value in am.volume]
        last_index = am.count - 1

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            self.bars_held += 1
            stop_hit = self.entry_price > 0 and bar.close_price <= self.entry_price * (1 - self.stop_loss_pct)
            time_exit = self.bars_held >= self.max_hold_days
            below_slow = bar.close_price < self.slow_ma0
            if cross_below or stop_hit or time_exit or below_slow:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.bars_held = 0
        else:
            signal = classify_pullback_bar(
                closes,
                volumes,
                last_index,
                ma_window=self.ma_window,
                pullback_band_pct=self.pullback_band_pct,
            )
            if signal == "buy" and self.fast_ma0 >= self.slow_ma0 * 0.995:
                orders = self.buy_stock(bar.close_price, volume)
                if orders:
                    self.entry_price = bar.close_price
                    self.bars_held = 0

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
