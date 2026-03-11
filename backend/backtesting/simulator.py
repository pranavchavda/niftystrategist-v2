"""Trade simulator — tracks position state and completed trades."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Trade:
    """A completed round-trip trade."""
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    quantity: int
    pnl: float
    pnl_pct: float
    exit_reason: str  # "sl", "target", "trailing", "squareoff", "entry_opposite"
    holding_minutes: int


@dataclass
class OpenPosition:
    """A currently open position."""
    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    entry_time: datetime
    quantity: int


class TradeSimulator:
    """Tracks position state and records completed trades."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.trades: list[Trade] = []
        self.position: OpenPosition | None = None

    def open_position(self, side: str, price: float, time: datetime, qty: int) -> None:
        """Open a new position. If one is already open, close it first."""
        if self.position is not None:
            # Close existing position before opening opposite
            self.close_position(price, time, "entry_opposite")
        self.position = OpenPosition(
            symbol=self.symbol,
            side=side,
            entry_price=price,
            entry_time=time,
            quantity=qty,
        )

    def close_position(self, price: float, time: datetime, reason: str) -> Trade | None:
        """Close the current position and record a completed trade."""
        if self.position is None:
            return None

        pos = self.position
        if pos.side == "long":
            pnl = (price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - price) * pos.quantity

        pnl_pct = (pnl / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price else 0.0
        holding_mins = int((time - pos.entry_time).total_seconds() / 60)

        trade = Trade(
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            exit_price=price,
            exit_time=time,
            quantity=pos.quantity,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            exit_reason=reason,
            holding_minutes=max(holding_mins, 0),
        )
        self.trades.append(trade)
        self.position = None
        return trade

    @property
    def is_flat(self) -> bool:
        return self.position is None

    @property
    def is_long(self) -> bool:
        return self.position is not None and self.position.side == "long"

    @property
    def is_short(self) -> bool:
        return self.position is not None and self.position.side == "short"
