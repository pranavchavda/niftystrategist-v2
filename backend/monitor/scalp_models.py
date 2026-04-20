"""Pydantic models for scalp session manager."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ScalpState(str, Enum):
    IDLE = "IDLE"
    # Options scalp states
    HOLDING_CE = "HOLDING_CE"
    HOLDING_PE = "HOLDING_PE"
    # Equity states (intraday & swing)
    HOLDING_LONG = "HOLDING_LONG"
    HOLDING_SHORT = "HOLDING_SHORT"


class SessionMode(str, Enum):
    OPTIONS_SCALP = "options_scalp"
    EQUITY_INTRADAY = "equity_intraday"
    EQUITY_SWING = "equity_swing"


# Map underlying short names to Upstox index instrument tokens.
# Same mapping as services/upstox_client.py:1557.
UNDERLYING_INSTRUMENT_MAP: dict[str, str] = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "NIFTY50": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "NIFTYBANK": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
}


class ScalpSessionConfig(BaseModel):
    """Immutable config set at creation time."""
    id: int = 0
    user_id: int = 0
    name: str = ""
    enabled: bool = True

    session_mode: str = SessionMode.OPTIONS_SCALP.value

    underlying: str = "NIFTY"
    underlying_instrument_token: str = ""
    expiry: str = ""           # Unused in equity modes
    lots: int = 1              # Used by options modes
    quantity: int | None = None  # Used by equity modes
    product: str = "I"

    indicator_timeframe: str = "1m"
    utbot_period: int = 10
    utbot_sensitivity: float = 1.0

    # Parametrized primary signal. utbot remains the default; other
    # supported indicators return a signed scalar so the same flip-detection
    # contract (prev<=0 → curr>0 = bullish) applies across the board.
    primary_indicator: str = "utbot"
    primary_params: dict[str, Any] | None = None
    # Optional confirm filter. On a primary flip, the confirm indicator's
    # current sign must agree before entry fires.
    confirm_indicator: str | None = None
    confirm_params: dict[str, Any] | None = None

    sl_points: float | None = None
    target_points: float | None = None
    trail_percent: float | None = None
    trail_points: float | None = None
    trail_arm_points: float | None = None
    squareoff_time: str = "15:15"

    max_trades: int = 20
    cooldown_seconds: int = 60

    # API→daemon signal: "exit_and_disable" or "exit_and_delete" when a user
    # tries to disable or delete a HOLDING session. Daemon clears after acting.
    pending_action: str | None = None


class ScalpSessionRuntime(BaseModel):
    """Mutable runtime state, updated by daemon."""
    state: ScalpState = ScalpState.IDLE
    current_option_type: str | None = None
    current_strike: float | None = None
    current_instrument_token: str | None = None
    current_tradingsymbol: str | None = None
    entry_price: float | None = None
    entry_time: datetime | None = None
    highest_premium: float | None = None
    trail_armed: bool = False
    last_premium_ltp: float | None = None
    trade_count: int = 0
    last_exit_time: datetime | None = None


class ScalpSession(BaseModel):
    """Complete in-memory session: config + runtime state."""
    config: ScalpSessionConfig
    runtime: ScalpSessionRuntime = ScalpSessionRuntime()

    @property
    def is_holding(self) -> bool:
        return self.runtime.state != ScalpState.IDLE

    @property
    def user_id(self) -> int:
        return self.config.user_id

    @property
    def id(self) -> int:
        return self.config.id
