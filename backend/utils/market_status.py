"""Market status utilities — shared between CLI tools and API endpoints."""

from datetime import datetime, timedelta, timezone

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

# NSE market hours (IST)
PREOPEN_START = (9, 0)   # 9:00 AM
MARKET_OPEN = (9, 15)    # 9:15 AM
MARKET_CLOSE = (15, 30)  # 3:30 PM

# Upstox API status values that indicate the market is open/trading
_OPEN_STATUSES = {"NormalOpen", "NORMAL_OPEN", "Open", "PreOpen", "PRE_OPEN", "PreOpenEnd"}
_CLOSED_STATUSES = {"Closed", "CLOSED", "NormalClose", "NORMAL_CLOSE", "PostClose", "POST_CLOSE"}


def _ist_now() -> datetime:
    """Get current time in IST."""
    return datetime.now(IST)


def get_next_trading_day(dt: datetime) -> datetime:
    """Get the next trading day (skipping weekends).

    Note: Without Upstox API, this can't skip exchange holidays.
    The API-based market status is the canonical source for that.
    """
    candidate = dt + timedelta(days=1)
    candidate = candidate.replace(hour=9, minute=15, second=0, microsecond=0)
    while candidate.weekday() >= 5:
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


def get_market_status(upstox_api_status: str | None = None) -> dict:
    """Determine current NSE market status.

    Args:
        upstox_api_status: If provided, the raw status string from the Upstox
            market status API (e.g. "NormalOpen", "Closed"). Used as the
            canonical source of truth for whether the market is open.

    Returns a dict with keys:
      - status: "open" | "pre_open" | "closed"
      - Additional keys depending on status (closes_in, next_open, reason, etc.)
    """
    now = _ist_now()
    weekday = now.weekday()

    today_preopen = now.replace(hour=PREOPEN_START[0], minute=PREOPEN_START[1], second=0, microsecond=0)
    today_open = now.replace(hour=MARKET_OPEN[0], minute=MARKET_OPEN[1], second=0, microsecond=0)
    today_close = now.replace(hour=MARKET_CLOSE[0], minute=MARKET_CLOSE[1], second=0, microsecond=0)

    # If Upstox API status is available, use it as source of truth
    if upstox_api_status:
        if upstox_api_status in _OPEN_STATUSES or "open" in upstox_api_status.lower():
            if upstox_api_status == "PreOpen" or now < today_open:
                return {
                    "status": "pre_open",
                    "reason": "pre_open_session",
                    "next_event": "market open",
                    "next_event_time": "9:15 AM IST",
                    "next_event_in": format_duration(today_open - now),
                    "current_time_ist": now.strftime("%I:%M %p IST"),
                    "source": "upstox_api",
                }
            return {
                "status": "open",
                "closes_in": format_duration(today_close - now),
                "close_time": "3:30 PM IST",
                "current_time_ist": now.strftime("%I:%M %p IST"),
                "source": "upstox_api",
            }
        else:
            # API says closed
            next_day = get_next_trading_day(now)
            reason = "weekend" if weekday >= 5 else "holiday_or_after_hours"
            return {
                "status": "closed",
                "reason": reason,
                "next_open": next_day.strftime("%a %b %d at 9:15 AM IST"),
                "next_open_in": format_duration(next_day - now),
                "current_time_ist": now.strftime("%I:%M %p IST"),
                "source": "upstox_api",
            }

    # Fallback: IST-based time calculation (weekends only, no holiday list)
    weekend = weekday >= 5

    if weekend:
        next_day = get_next_trading_day(now)
        return {
            "status": "closed",
            "reason": "weekend",
            "next_open": next_day.strftime("%a %b %d at 9:15 AM IST"),
            "next_open_in": format_duration(next_day - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
            "source": "time_based",
        }

    if now < today_preopen:
        return {
            "status": "closed",
            "reason": "before_hours",
            "next_event": "pre-open",
            "next_event_time": "9:00 AM IST",
            "next_event_in": format_duration(today_preopen - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
            "source": "time_based",
        }
    elif now < today_open:
        return {
            "status": "pre_open",
            "reason": "pre_open_session",
            "next_event": "market open",
            "next_event_time": "9:15 AM IST",
            "next_event_in": format_duration(today_open - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
            "source": "time_based",
        }
    elif now < today_close:
        return {
            "status": "open",
            "closes_in": format_duration(today_close - now),
            "close_time": "3:30 PM IST",
            "current_time_ist": now.strftime("%I:%M %p IST"),
            "source": "time_based",
        }
    else:
        next_day = get_next_trading_day(now)
        return {
            "status": "closed",
            "reason": "after_hours",
            "next_open": next_day.strftime("%a %b %d at 9:15 AM IST"),
            "next_open_in": format_duration(next_day - now),
            "current_time_ist": now.strftime("%I:%M %p IST"),
            "source": "time_based",
        }
