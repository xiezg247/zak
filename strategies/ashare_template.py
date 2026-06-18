from datetime import date

from vnpy.trader.constant import Direction, Interval, Offset
from vnpy_ctastrategy import ArrayManager, CtaTemplate, TradeData

from vnpy_ashare.config.runtime import normalize_volume


class AShareTemplate(CtaTemplate):
    """
    A 股策略基类

    - 仅做多（不提供 short / cover）
    - 100 股整数倍下单
    - T+1：当日买入次日方可卖出
    """

    last_buy_date: date | None = None

    def indicator_warmup_bars(self) -> int:
        """指标预热所需 K 线根数（须与 ArrayManager.size 一致）。"""
        slow = int(getattr(self, "slow_window", 0) or 0)
        fast = int(getattr(self, "fast_window", 0) or 0)
        extra = int(getattr(self, "breakout_lookback", 0) or 0)
        adx = int(getattr(self, "adx_period", 0) or 0)
        return max(slow, fast, extra, adx, 1) + 5

    def init_array_manager(self) -> ArrayManager:
        """按策略窗口初始化 ArrayManager，避免短区间回测永远 inited=False。"""
        return ArrayManager(self.indicator_warmup_bars())

    def load_indicator_bars(self, *, interval: Interval = Interval.DAILY) -> None:
        self.load_bar(self.indicator_warmup_bars(), interval=interval)

    def round_volume(self, volume: int) -> int:
        return normalize_volume(volume)

    def buy_stock(self, price: float, volume: int) -> list:
        """买入股票（整手）"""
        if self.pos > 0:
            return []
        return self.buy(price, self.round_volume(volume))

    def sell_stock(self, price: float, volume: int, trading_day: date) -> list:
        """卖出股票（整手，遵守 T+1）"""
        if self.pos <= 0:
            return []

        if self.last_buy_date is not None and trading_day <= self.last_buy_date:
            return []

        sell_volume = min(self.round_volume(volume), abs(self.pos))
        return self.sell(price, sell_volume)

    def on_trade(self, trade: TradeData) -> None:
        if trade.direction == Direction.LONG and trade.offset == Offset.OPEN:
            self.last_buy_date = trade.datetime.date()
        self.put_event()
