"""Orchestrator capabilities — composable units of agent behavior.

Each capability is an `AbstractCapability` subclass that injects instructions,
settings, toolsets, or hooks. This package starts with context-injection
capabilities migrated out of the orchestrator's `_register_dynamic_instructions()`.

All capability-driven injection is gated behind the ENABLE_CAPABILITIES_V2 env
flag. When off (default), the orchestrator's legacy inline instruction path
runs unchanged. This lets the capability path bake on dev before cutover.
"""

import os

from agents.capabilities.context_injection import (
    MemoryCapability,
    RecentThreadsCapability,
    DateTimeCapability,
)

__all__ = [
    "MemoryCapability",
    "RecentThreadsCapability",
    "DateTimeCapability",
    "capabilities_v2_enabled",
]


def capabilities_v2_enabled() -> bool:
    """True when the capabilities-v2 path should be used instead of the
    orchestrator's legacy inline instruction injection.

    Controlled by the ENABLE_CAPABILITIES_V2 env var (default off). Accepts
    "1", "true", "yes", "on" (case-insensitive) as truthy.
    """
    return os.getenv("ENABLE_CAPABILITIES_V2", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
