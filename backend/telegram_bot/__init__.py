"""Telegram bot service — inbound message handling per user.

This package runs *inside* the FastAPI process. The outbound notifier in
`services.telegram_notifier` is independent and can be called from any
process (the monitor daemon, the scheduler, etc.).

See docs/plans/2026-05-20-telegram-integration.md.
"""

from . import manager

__all__ = ["manager"]
