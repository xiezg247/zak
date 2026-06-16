"""A 股交易时段判断。"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from vnpy.trader.utility import ZoneInfo

from vnpy_ashare.domain.calendar import is_trading_day

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
    """交易日 9:30–11:30、13:00–15:00（含节假日排除）。"""
    now = _to_china_time(dt or datetime.now(CHINA_TZ))
    if not is_trading_day(now.date()):
        return False
    current = now.time()
    if MORNING_OPEN <= current <= MORNING_CLOSE:
        return True
    if AFTERNOON_OPEN <= current <= AFTERNOON_CLOSE:
        return True
    return False


def ashare_market_phase(dt: datetime | None = None) -> str:
    """A 股市场阶段：intraday | post_close | pre_open | closed。"""
    now = _to_china_time(dt or datetime.now(CHINA_TZ))
    if not is_trading_day(now.date()):
        return "closed"
    current = now.time()
    if is_ashare_trading_session(now):
        return "intraday"
    if current >= AFTERNOON_CLOSE:
        return "post_close"
    return "pre_open"


_MARKET_PHASE_LABELS = {
    "intraday": "盘中",
    "post_close": "盘后",
    "pre_open": "盘前",
    "closed": "休市",
}


def ashare_market_phase_label(dt: datetime | None = None) -> str:
    """盘中 / 盘后 / 盘前 / 休市 展示文案。"""
    return _MARKET_PHASE_LABELS.get(ashare_market_phase(dt), "休市")


def _next_session_start_after(dt: datetime) -> datetime:
    """返回严格晚于 dt 的下一段连续竞价开始时刻。"""
    probe = dt
    for _ in range(500):
        day = probe.date()
        if is_trading_day(day):
            for session_start in (MORNING_OPEN, AFTERNOON_OPEN):
                start = datetime.combine(day, session_start, tzinfo=CHINA_TZ)
                if start > probe:
                    return start
        probe = datetime.combine(day + timedelta(days=1), time.min, tzinfo=CHINA_TZ)
    raise RuntimeError("未找到下一交易时段")


def screen_after_collect_delay_seconds() -> int:
    """盘中选股相对行情采集的默认延迟（秒）。"""
    import os

    raw = os.getenv("SCREEN_AFTER_COLLECT_SEC", "90").strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return 90


def next_intraday_screen_at(
    now: datetime | None = None,
    *,
    collect_interval_seconds: int = 30,
) -> datetime:
    """建议的下次盘中选股时刻：交易时段内为「下次采集 + 延迟」，其余为下一段开盘后延迟。"""
    current = _to_china_time(now or datetime.now(CHINA_TZ))
    delay = timedelta(seconds=screen_after_collect_delay_seconds())
    interval = max(collect_interval_seconds, 1)

    if is_ashare_trading_session(current):
        next_collect = next_quotes_collect_at(current, interval_seconds=interval)
        if is_ashare_trading_session(next_collect):
            return next_collect + delay
        return _next_session_start_after(current) + delay
    return _next_session_start_after(current) + delay


def next_quotes_collect_at(
    now: datetime | None = None,
    *,
    interval_seconds: int = 15,
) -> datetime:
    """计算下一次自动行情采集时间（交易时段内按间隔，其余休眠至下一段开盘）。"""
    current = _to_china_time(now or datetime.now(CHINA_TZ))
    interval = max(interval_seconds, 1)

    if is_ashare_trading_session(current):
        candidate = current + timedelta(seconds=interval)
        if is_ashare_trading_session(candidate):
            return candidate

    return _next_session_start_after(current)


def default_chart_tab_index(dt: datetime | None = None) -> int:
    """交易时段默认分时，其余默认日 K。"""
    return INTRADAY_CHART_TAB if is_ashare_trading_session(dt) else DAILY_CHART_TAB


def elapsed_trading_minutes(dt: datetime | None = None) -> float:
    """当日已开盘交易分钟数（午休不计；收盘后返回全日 240 分钟）。"""
    now = _to_china_time(dt or datetime.now(CHINA_TZ))
    if not is_trading_day(now.date()):
        return 0.0
    current = now.time()
    if current < MORNING_OPEN:
        return 0.0
    if current >= AFTERNOON_CLOSE:
        return float(INTRADAY_SESSION_MINUTES)
    return max(bar_session_minute(now), 1.0)


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
