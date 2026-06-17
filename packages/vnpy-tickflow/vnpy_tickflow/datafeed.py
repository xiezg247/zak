"""VeighNa TickFlow 数据源适配。"""

from __future__ import annotations

from collections.abc import Callable

from tickflow import TickFlow
from vnpy.trader.datafeed import BaseDatafeed
from vnpy.trader.object import BarData, HistoryRequest
from vnpy.trader.setting import SETTINGS

from vnpy_tickflow.client import get_tickflow_client, is_free_mode
from vnpy_tickflow.klines import dataframe_to_bars, fetch_klines_paged
from vnpy_tickflow.mapping import (
    ASHARE_EXCHANGES,
    CHINA_TZ,
    FREE_PERIODS,
    interval_to_period,
    to_tf_symbol,
)


class TickflowDatafeed(BaseDatafeed):
    """TickFlow 数据服务接口。"""

    def __init__(self) -> None:
        self.api_key: str = SETTINGS.get("datafeed.password", "")
        self.username: str = SETTINGS.get("datafeed.username", "")
        self.inited: bool = False
        self.client: TickFlow | None = None
        self.free_mode: bool = False

    def init(self, output: Callable = print) -> bool:
        if self.inited:
            return True

        self.client = get_tickflow_client(api_key=self.api_key)
        self.free_mode = is_free_mode(api_key=self.api_key)
        if self.free_mode:
            output("TickFlow 数据服务初始化成功（免费日K服务）")
        else:
            output("TickFlow 数据服务初始化成功（完整服务）")

        self.inited = True
        return True

    def query_bar_history(
        self,
        req: HistoryRequest,
        output: Callable = print,
    ) -> list[BarData]:
        if not self.inited:
            self.init(output)

        assert self.client is not None

        if req.exchange not in ASHARE_EXCHANGES:
            output(f"提示: {req.exchange.value} 非 A 股交易所，本项目主要针对沪深京 A 股优化")

        tf_symbol = to_tf_symbol(req.symbol, req.exchange)
        if not tf_symbol:
            output(f"TickFlow 不支持该交易所: {req.exchange}")
            return []

        if req.interval is None:
            output("TickFlow 缺少 K 线周期")
            return []

        period = interval_to_period(req.interval)
        if not period:
            output(f"TickFlow 不支持该周期: {req.interval}")
            return []

        if self.free_mode and period not in FREE_PERIODS:
            output("免费 TickFlow 服务仅支持日K及以上周期，请配置 TICKFLOW_API_KEY 后使用分钟线")
            return []

        if req.start is None or req.end is None:
            output("TickFlow 缺少起止时间")
            return []

        start_ms = int(req.start.replace(tzinfo=CHINA_TZ).timestamp() * 1000)
        end_ms = int(req.end.replace(tzinfo=CHINA_TZ).timestamp() * 1000)

        try:
            df = fetch_klines_paged(self.client, tf_symbol, period, start_ms, end_ms)
        except Exception as ex:
            output(f"TickFlow 查询失败: {ex}")
            return []

        if df.empty:
            return []

        interval = req.interval
        if interval is None:
            return []

        return dataframe_to_bars(
            df,
            symbol=req.symbol,
            exchange=req.exchange,
            interval=interval,
            gateway_name="TF",
        )
