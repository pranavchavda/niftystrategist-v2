"""Market status utilities — shared between CLI tools and API endpoints."""

from datetime import datetime, timedelta, timezone

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# NSE market hours (IST)
PREOPEN_START = (9, 0)   # 9:00 AM
MARKET_OPEN = (9, 15)    # 9:15 AM
MARKET_CLOSE = (15, 30)  # 3:30 PM

# NSE holidays 2026 (dates in MM-DD format)
NSE_HOLIDAYS_2026 = [
    "01-26",  # Republic Day
    "02-17",  # Mahashivratri
    "03-10",  # Holi
    "03-31",  # Id-Ul-Fitr
    "04-02",  # Ram Navami
    "04-14",  # Dr. Ambedkar Jayanti
    "04-18",  # Good Friday
    "05-01",  # Maharashtra Day
    "06-07",  # Id-Ul-Adha
    "07-07",  # Muharram
    "08-15",  # Independence Day
    "08-19",  # Janmashtami
    "09-05",  # Milad-Un-Nabi
    "10-02",  # Mahatma Gandhi Jayanti
    "10-20",  # Dussehra
    "10-21",  # Dussehra (additional)
    "11-09",  # Diwali (Laxmi Pujan)
    "11-10",  # Diwali Balipratipada
    "11-27",  # Guru Nanak Jayanti
    "12-25",  # Christmas
]


def is_holiday(dt: datetime) -> bool:
    """Check if given IST date is an NSE holiday."""
    return dt.strftime("%m-%d") in NSE_HOLIDAYS_2026


def get_next_trading_day(dt: datetime) -> datetime:
    """Get the next trading day (skipping weekends and holidays)."""
    candidate = dt + timedelta(days=1)
    candidate = candidate.replace(hour=9, minute=15, second=0, microsecond=0)
    while candidate.weekday() >= 5 or is_holiday(candidate):
        candidate += timedelta(days=1)
    return candidate


def format_duration(td: timedelta) -> str:
    """Format a timedelta as '2h 15m' or '45m'."""
    total_minutes = int(td.total_seconds() / 60)
    if total_minutes < 0:
        return "0m"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def get_market_status() -> dict:
    """Determine current NSE market status.

    Returns a dict with keys:
      - status: "open" | "pre_open" | "closed"
      - Additional keys depending on status (closes_in, next_open, reason, etc.)
    """
    now = datetime.now(IST)
    weekday = now.weekday()

    today_preopen = now.replace(hour=PREOPEN_START[0], minute=PREOPEN_START[1], second=0, microsecond=0)
    today_open = now.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1], second=0, microsecond=0)
    today_close = now.replace(hour=MARKET_CLOSE[0], minute=MARKET_CLOSE[1], second=0, microsecond=0)

    holiday = is_holiday(now)
    weekend = weekday >= 5

    if weekend or holiday:
        next_day = get_next_trading_day(now)
        reason = "weekend" if weekend else "holiday"
        return {
            "status": "closed",
            "reason": reason,
            "next_open": next_day.strftime("%a %b %d at 9:15 AM IST"),
            "next_open_in": format_duration(next_day - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
        }

    if now < today_preopen:
        return {
            "status": "closed",
            "reason": "before_hours",
            "next_event": "pre-open",
            "next_event_time": "9:00 AM IST",
            "next_event_in": format_duration(today_preopen - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
        }
    elif now < today_open:
        return {
            "status": "pre_open",
            "reason": "pre_open_session",
            "next_event": "market open",
            "next_event_time": "9:15 AM IST",
            "next_event_in": format_duration(today_open - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
        }
    elif now < today_close:
        return {
            "status": "open",
            "closes_in": format_duration(today_close - now),
            "close_time": "3:30 PM IST",
            "current_time_ist": now.strftime("%I:%M %p IST"),
        }
    else:
        next_day = get_next_trading_day(now)
        return {
            "status": "closed",
            "reason": "after_hours",
            "next_open": next_day.strftime("%a %b %d at 9:15 AM IST"),
            "next_open_in": format_duration(next_day - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
        }
