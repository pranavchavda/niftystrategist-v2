"""
Datetime utilities for consistent timezone handling.

The database uses TIMESTAMP WITHOUT TIME ZONE columns (naive datetimes),
but Python 3.12+ deprecates datetime.utcnow() in favor of timezone-aware datetimes.

This module provides helper functions to bridge the gap:
- Use timezone-aware datetimes in application code (datetime.now(timezone.utc))
- Convert to naive UTC datetimes when storing to database
"""

from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Return current UTC time as a naive datetime (no timezone info).

    Use this function when:
    - Creating database records with timestamp columns
    - Comparing with timestamps from the database

    The returned datetime has no tzinfo but represents UTC time.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convert a timezone-aware datetime to naive UTC.

    Args:
        dt: A datetime object (can be timezone-aware or naive)

    Returns:
        A naive datetime in UTC, or None if input is None
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        # Convert to UTC first, then strip timezone
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    # Already naive, assume it's UTC
    return dt
