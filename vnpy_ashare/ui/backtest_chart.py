"""回测结果图表：兼容 pandas 2.x + pyqtgraph。"""

from __future__ import annotations

import numpy as np
from pandas import DataFrame
from vnpy_ctabacktester.ui.widget import BacktesterChart


class AshareBacktesterChart(BacktesterChart):
    """
    vnpy 原实现将 df['balance'] 直接传给 pyqtgraph，在 DatetimeIndex 下会 KeyError: 0。
    """

    def set_data(self, df: DataFrame) -> None:
        if df is None:
            return

        self.dates.clear()
        for n, date in enumerate(df.index):
            self.dates[n] = date

        balance = df["balance"].to_numpy()
        drawdown = df["drawdown"].to_numpy()
        net_pnl = df["net_pnl"].to_numpy()

        self.balance_curve.setData(balance)
        self.drawdown_curve.setData(drawdown)

        profit_pnl_x: list[int] = []
        profit_pnl_height: list[float] = []
        loss_pnl_x: list[int] = []
        loss_pnl_height: list[float] = []

        for count, pnl in enumerate(net_pnl):
            if pnl >= 0:
                profit_pnl_height.append(float(pnl))
                profit_pnl_x.append(count)
            else:
                loss_pnl_height.append(float(pnl))
                loss_pnl_x.append(count)

        self.profit_pnl_bar.setOpts(x=profit_pnl_x, height=profit_pnl_height)
        self.loss_pnl_bar.setOpts(x=loss_pnl_x, height=loss_pnl_height)

        hist, x = np.histogram(net_pnl, bins="auto")
        x = x[:-1]
        self.distribution_curve.setData(x, hist)
