from vnpy_ctastrategy import (
    ArrayManager,
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from .ashare_template import AShareTemplate


class AshareSwingMaStrategy(AShareTemplate):
    """A 股波段双均线 + 缩量回踩慢线入场（仅做多、T+1）"""

    author = "zak"

    fast_window: int = 10
    slow_window: int = 20
    pullback_pct: float = 2.0
    pullback_wait_days: int = 5
    stop_loss_pct: float = 0.05
    trade_volume: int = 100

    fast_ma0: float = 0.0
    fast_ma1: float = 0.0
    slow_ma0: float = 0.0
    slow_ma1: float = 0.0
    pending_pullback: bool = False
    pullback_wait_bars: int = 0
    entry_price: float = 0.0

    parameters = [
        "fast_window",
        "slow_window",
        "pullback_pct",
        "pullback_wait_days",
        "stop_loss_pct",
        "trade_volume",
    ]
    variables = [
        "fast_ma0",
        "fast_ma1",
        "slow_ma0",
        "slow_ma1",
        "pending_pullback",
        "pullback_wait_bars",
        "entry_price",
    ]

    def on_init(self) -> None:
        self.write_log("A股波段回踩均线策略初始化")
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

    def _is_pullback(self, bar: BarData, am: ArrayManager) -> bool:
        if self.slow_ma0 <= 0:
            return False
        band = self.pullback_pct / 100.0
        lower = self.slow_ma0 * (1 - band)
        upper = self.slow_ma0 * (1 + band)
        if not (lower <= bar.close_price <= upper):
            return False
        if am.count < 6:
            return False
        recent_avg = float(am.volume[-6:-1].sum()) / 5
        if recent_avg <= 0:
            return True
        return float(bar.volume) < recent_avg

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

        if cross_over and self.pos <= 0:
            self.pending_pullback = True
            self.pullback_wait_bars = 0

        if cross_below:
            self.pending_pullback = False
            self.pullback_wait_bars = 0

        if self.pos > 0:
            stop_hit = self.entry_price > 0 and bar.close_price <= self.entry_price * (1 - self.stop_loss_pct)
            structure_break = bar.close_price < self.slow_ma0
            if cross_below or stop_hit or structure_break:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.pending_pullback = False
                self.pullback_wait_bars = 0
        elif self.pending_pullback:
            self.pullback_wait_bars += 1
            if self.pullback_wait_bars > self.pullback_wait_days:
                self.pending_pullback = False
                self.pullback_wait_bars = 0
            elif self._is_pullback(bar, am) and self.fast_ma0 > self.slow_ma0:
                orders = self.buy_stock(bar.close_price, volume)
                if orders:
                    self.entry_price = bar.close_price
                    self.pending_pullback = False
                    self.pullback_wait_bars = 0

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
