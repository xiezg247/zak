"""A 股极致短线·半路（日 K 涨幅 3–7% + 放量，T+1）。"""

from __future__ import annotations

from vnpy_ctastrategy import (
    ArrayManager,
    BarData,
    BarGenerator,
    OrderData,
    StopOrder,
    TickData,
)

from strategies.ultra_short_signals import classify_intraday_breakout_bar

from .ashare_template import AShareTemplate


class AshareIntradayBreakoutStrategy(AShareTemplate):
    """带量拉升半路买入；止损/止盈/持仓天数或死叉卖出。"""

    author = "zak"

    fast_window: int = 5
    slow_window: int = 10
    min_change_pct: float = 3.0
    max_change_pct: float = 7.0
    volume_ratio_min: float = 1.2
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.08
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
        "min_change_pct",
        "max_change_pct",
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

    def indicator_warmup_bars(self) -> int:
        return max(self.slow_window, 10) + 5

    def on_init(self) -> None:
        self.write_log("A股极致短线·半路策略初始化")
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
        if am.count < max(self.slow_window, 10) + 2:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]
        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1

        closes = [float(value) for value in am.close]
        highs = [float(value) for value in am.high]
        volumes = [float(value) for value in am.volume]
        symbol = bar.vt_symbol.split(".", 1)[0]
        last_index = am.count - 1

        trading_day = bar.datetime.date()
        volume = self.round_volume(self.trade_volume)

        if self.pos > 0:
            self.bars_held += 1
            stop_hit = self.entry_price > 0 and bar.close_price <= self.entry_price * (1 - self.stop_loss_pct)
            profit_hit = self.entry_price > 0 and bar.close_price >= self.entry_price * (1 + self.take_profit_pct)
            time_exit = self.bars_held >= self.max_hold_days
            if cross_below or stop_hit or profit_hit or time_exit:
                self.sell_stock(bar.close_price, abs(self.pos) or volume, trading_day)
                self.entry_price = 0.0
                self.bars_held = 0
        else:
            signal, _change = classify_intraday_breakout_bar(
                closes,
                highs,
                volumes,
                last_index,
                symbol=symbol,
                min_change_pct=self.min_change_pct,
                max_change_pct=self.max_change_pct,
                volume_ratio_min=self.volume_ratio_min,
            )
            if signal == "buy" and self.fast_ma0 > self.slow_ma0:
                orders = self.buy_stock(bar.close_price, volume)
                if orders:
                    self.entry_price = bar.close_price
                    self.bars_held = 0

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
