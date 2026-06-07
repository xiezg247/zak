from collections.abc import Callable
from datetime import datetime, timedelta
import os

import pandas as pd
from tickflow import TickFlow

from vnpy.trader.constant import Exchange, Interval

# 本项目聚焦 A 股，其他市场仅作扩展保留
ASHARE_EXCHANGES = frozenset({Exchange.SSE, Exchange.SZSE, Exchange.BSE})
from vnpy.trader.datafeed import BaseDatafeed
from vnpy.trader.object import BarData, HistoryRequest
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import ZoneInfo, round_to

CHINA_TZ = ZoneInfo("Asia/Shanghai")

EXCHANGE_VT2TF: dict[Exchange, str] = {
    Exchange.SSE: "SH",
    Exchange.SZSE: "SZ",
    Exchange.BSE: "BJ",
    Exchange.SHFE: "SHF",
    Exchange.DCE: "DCE",
    Exchange.CZCE: "ZCE",
    Exchange.CFFEX: "CFX",
    Exchange.INE: "INE",
    Exchange.GFEX: "GFE",
    Exchange.SEHK: "HK",
    Exchange.NASDAQ: "US",
    Exchange.NYSE: "US",
    Exchange.AMEX: "US",
}

INTERVAL_VT2TF: dict[Interval, str] = {
    Interval.MINUTE: "1m",
    Interval.HOUR: "60m",
    Interval.DAILY: "1d",
    Interval.WEEKLY: "1w",
}

INTERVAL_ADJUSTMENT_MAP: dict[Interval, timedelta] = {
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(),
    Interval.WEEKLY: timedelta(),
}

FREE_PERIODS = {"1d", "1w", "1M", "1Q", "1Y"}
MAX_BARS_PER_REQUEST = 10000


def to_tf_symbol(symbol: str, exchange: Exchange) -> str | None:
    """将 VeighNa 合约代码转换为 TickFlow 代码格式"""
    suffix = EXCHANGE_VT2TF.get(exchange)
    if not suffix:
        return None
    return f"{symbol}.{suffix}"


def parse_datetime(value: str | int | float, interval: Interval) -> datetime:
    """解析 TickFlow 返回的时间字段"""
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value / 1000, tz=CHINA_TZ)
    else:
        text = str(value)
        if len(text) == 8:
            dt = datetime.strptime(text, "%Y%m%d")
        elif " " in text:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(text, "%Y-%m-%d")
        dt = dt.replace(tzinfo=CHINA_TZ)

    adjustment = INTERVAL_ADJUSTMENT_MAP.get(interval, timedelta())
    return dt - adjustment


class TickflowDatafeed(BaseDatafeed):
    """TickFlow 数据服务接口"""

    def __init__(self) -> None:
        self.api_key: str = SETTINGS.get("datafeed.password", "")
        self.username: str = SETTINGS.get("datafeed.username", "")
        self.inited: bool = False
        self.client: TickFlow | None = None
        self.free_mode: bool = False

    def init(self, output: Callable = print) -> bool:
        if self.inited:
            return True

        api_key = self.api_key or os.getenv("TICKFLOW_API_KEY", "")
        if api_key:
            self.client = TickFlow(api_key=api_key)
            self.free_mode = False
            output("TickFlow 数据服务初始化成功（完整服务）")
        else:
            self.client = TickFlow.free()
            self.free_mode = True
            output("TickFlow 数据服务初始化成功（免费日K服务）")

        self.inited = True
        return True

    def query_bar_history(
        self,
        req: HistoryRequest,
        output: Callable = print,
    ) -> list[BarData] | None:
        if not self.inited:
            self.init(output)

        assert self.client is not None

        if req.exchange not in ASHARE_EXCHANGES:
            output(
                f"提示: {req.exchange.value} 非 A 股交易所，"
                "本项目主要针对沪深京 A 股优化"
            )

        tf_symbol = to_tf_symbol(req.symbol, req.exchange)
        if not tf_symbol:
            output(f"TickFlow 不支持该交易所: {req.exchange}")
            return []

        period = INTERVAL_VT2TF.get(req.interval)
        if not period:
            output(f"TickFlow 不支持该周期: {req.interval}")
            return []

        if self.free_mode and period not in FREE_PERIODS:
            output(
                "免费 TickFlow 服务仅支持日K及以上周期，"
                "请配置 TICKFLOW_API_KEY 后使用分钟线"
            )
            return []

        start_ms = int(req.start.replace(tzinfo=CHINA_TZ).timestamp() * 1000)
        end_ms = int(req.end.replace(tzinfo=CHINA_TZ).timestamp() * 1000)

        try:
            frames = self._fetch_klines(tf_symbol, period, start_ms, end_ms)
        except Exception as ex:
            output(f"TickFlow 查询失败: {ex}")
            return []

        if not frames:
            return []

        df = pd.concat(frames, ignore_index=True).drop_duplicates(
            subset=["timestamp"], keep="last"
        )

        bars: list[BarData] = []
        for _, row in df.iterrows():
            if pd.isna(row.get("open")):
                continue

            if "trade_time" in row and pd.notna(row["trade_time"]):
                dt = parse_datetime(row["trade_time"], req.interval)
            elif "timestamp" in row and pd.notna(row["timestamp"]):
                dt = parse_datetime(row["timestamp"], req.interval)
            elif "trade_date" in row and pd.notna(row["trade_date"]):
                dt = parse_datetime(row["trade_date"], req.interval)
            else:
                continue

            turnover = row.get("amount", 0)
            if pd.isna(turnover):
                turnover = 0

            volume = row.get("volume", 0)
            if pd.isna(volume):
                volume = 0

            bar = BarData(
                symbol=req.symbol,
                exchange=req.exchange,
                interval=req.interval,
                datetime=dt,
                open_price=round_to(float(row["open"]), 0.000001),
                high_price=round_to(float(row["high"]), 0.000001),
                low_price=round_to(float(row["low"]), 0.000001),
                close_price=round_to(float(row["close"]), 0.000001),
                volume=float(volume),
                turnover=float(turnover),
                open_interest=0,
                gateway_name="TF",
            )
            bars.append(bar)

        bars.sort(key=lambda item: item.datetime)
        return bars

    def _fetch_klines(
        self,
        tf_symbol: str,
        period: str,
        start_ms: int,
        end_ms: int,
    ) -> list[pd.DataFrame]:
        """分页拉取 K 线，TickFlow 单次默认仅返回 100 根，需显式 count 并分页"""
        assert self.client is not None

        frames: list[pd.DataFrame] = []
        cursor_start = start_ms

        while cursor_start <= end_ms:
            df = self.client.klines.get(
                tf_symbol,
                period=period,
                start_time=cursor_start,
                end_time=end_ms,
                count=MAX_BARS_PER_REQUEST,
                adjust="forward",
                as_dataframe=True,
            )
            if df is None or df.empty:
                break

            frames.append(df)
            if len(df) < MAX_BARS_PER_REQUEST:
                break

            last_ts = int(df.iloc[-1]["timestamp"])
            if last_ts >= end_ms:
                break
            cursor_start = last_ts + 1

        return frames
