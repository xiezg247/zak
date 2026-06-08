"""A 股交易时段判断。"""

from __future__ import annotations

from datetime import datetime, time

from vnpy.trader.utility import ZoneInfo

CHINA_TZ = ZoneInfo("Asia/Shanghai")

MORNING_OPEN = time(9, 30)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(13, 0)
AFTERNOON_CLOSE = time(15, 0)

INTRADAY_CHART_TAB = 0
DAILY_CHART_TAB = 1

# TickFlow / A 股行情成交量单位为「手」
ASHARE_LOT_SIZE = 100

MORNING_OPEN_MIN = MORNING_OPEN.hour * 60 + MORNING_OPEN.minute
MORNING_CLOSE_MIN = MORNING_CLOSE.hour * 60 + MORNING_CLOSE.minute
AFTERNOON_OPEN_MIN = AFTERNOON_OPEN.hour * 60 + AFTERNOON_OPEN.minute
AFTERNOON_CLOSE_MIN = AFTERNOON_CLOSE.hour * 60 + AFTERNOON_CLOSE.minute
MORNING_SESSION_MINUTES = MORNING_CLOSE_MIN - MORNING_OPEN_MIN
AFTERNOON_SESSION_MINUTES = AFTERNOON_CLOSE_MIN - AFTERNOON_OPEN_MIN
INTRADAY_SESSION_MINUTES = MORNING_SESSION_MINUTES + AFTERNOON_SESSION_MINUTES


def _to_china_time(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=CHINA_TZ)
    return dt.astimezone(CHINA_TZ)


def is_ashare_trading_session(dt: datetime | None = None) -> bool:
    """工作日 9:30–11:30、13:00–15:00（不含节假日）。"""
    now = _to_china_time(dt or datetime.now(CHINA_TZ))
    if now.weekday() >= 5:
        return False
    current = now.time()
    if MORNING_OPEN <= current <= MORNING_CLOSE:
        return True
    if AFTERNOON_OPEN <= current <= AFTERNOON_CLOSE:
        return True
    return False


def default_chart_tab_index(dt: datetime | None = None) -> int:
    """交易时段默认分时，其余默认日 K。"""
    return INTRADAY_CHART_TAB if is_ashare_trading_session(dt) else DAILY_CHART_TAB


def bar_session_minute(dt: datetime) -> float:
    """将 bar 时间映射为连续交易分钟序号（午休不占位，避免折线横跨空白区）。"""
    local = _to_china_time(dt)
    minute_of_day = local.hour * 60 + local.minute + local.second / 60.0
    if minute_of_day < MORNING_OPEN_MIN:
        return 0.0
    if minute_of_day <= MORNING_CLOSE_MIN:
        return minute_of_day - MORNING_OPEN_MIN
    if minute_of_day < AFTERNOON_OPEN_MIN:
        return float(MORNING_SESSION_MINUTES)
    if minute_of_day <= AFTERNOON_CLOSE_MIN:
        return MORNING_SESSION_MINUTES + (minute_of_day - AFTERNOON_OPEN_MIN)
    return float(INTRADAY_SESSION_MINUTES)


def session_minute_to_time_label(session_min: float) -> str:
    """交易分钟序号 → HH:MM（午休压缩坐标）。"""
    if session_min < MORNING_SESSION_MINUTES:
        total_min = MORNING_OPEN_MIN + session_min
    else:
        total_min = AFTERNOON_OPEN_MIN + (session_min - MORNING_SESSION_MINUTES)
    hour = int(total_min) // 60
    minute = int(total_min) % 60
    return f"{hour:02d}:{minute:02d}"


def intraday_axis_ticks() -> list[tuple[float, str]]:
    """分时图常用时间刻度（午休压缩后 13:00 接在 11:30 之后）。"""
    return [
        (0.0, "09:30"),
        (60.0, "10:30"),
        (float(MORNING_SESSION_MINUTES), "11:30/13:00"),
        (float(MORNING_SESSION_MINUTES + 60), "14:00"),
        (float(INTRADAY_SESSION_MINUTES), "15:00"),
    ]


def vwap_price(amount: float, volume_lots: float) -> float:
    """成交额 / 成交量（手）→ 均价。"""
    shares = volume_lots * ASHARE_LOT_SIZE
    if shares <= 0:
        return 0.0
    return amount / shares
