from datetime import date

from vnpy.trader.constant import Direction, Offset
from vnpy_ctastrategy import CtaTemplate, TradeData

from vnpy_ashare.config import normalize_volume


class AShareTemplate(CtaTemplate):
    """
    A 股策略基类

    - 仅做多（不提供 short / cover）
    - 100 股整数倍下单
    - T+1：当日买入次日方可卖出
    """

    last_buy_date: date | None = None

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
