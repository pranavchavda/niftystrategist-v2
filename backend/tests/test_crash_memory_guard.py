"""Phase 2 — interrupted/crashed-turn memory guard.

A crashed awakening writes a partial summary tagged extra_metadata.crashed=True.
The daily extractor must exclude only that tagged turn, not the whole thread.
See docs/plans/2026-05-23-prefix-cache-memory-port.md.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.extract_memories_daily import _is_crashed_message  # noqa: E402


def _msg(role, content, meta=None):
    return SimpleNamespace(role=role, content=content, extra_metadata=meta)


def test_crash_tagged_message_detected():
    assert _is_crashed_message(_msg("assistant", "partial", {"crashed": True})) is True


def test_normal_messages_not_flagged():
    assert _is_crashed_message(_msg("user", "hi", None)) is False
    assert _is_crashed_message(_msg("assistant", "ok", {"auto_followup": True})) is False
    assert _is_crashed_message(_msg("assistant", "ok", {})) is False
    # crashed falsey -> not excluded
    assert _is_crashed_message(_msg("assistant", "ok", {"crashed": False})) is False


def test_non_dict_metadata_safe():
    assert _is_crashed_message(_msg("assistant", "ok", "weird")) is False
    assert _is_crashed_message(SimpleNamespace(role="assistant", content="x")) is False


def test_only_crashed_turn_excluded_thread_survives():
    """The filter excludes only the tagged turn; good surrounding turns remain."""
    messages = [
        _msg("user", "deploy ORB on NIFTY"),
        _msg("assistant", "Deployed ORB strategy with SL at 24800."),
        _msg("assistant", "⚠️ Awakening crashed — partial summary", {"crashed": True}),
        _msg("user", "what's my risk per trade?"),
        _msg("assistant", "₹2000 per trade per your mandate."),
    ]
    kept = [m for m in messages if not _is_crashed_message(m)]
    assert len(kept) == 4
    assert all(not _is_crashed_message(m) for m in kept)
    # The durable facts around the crash are preserved.
    contents = " ".join(m.content for m in kept)
    assert "ORB strategy" in contents
    assert "₹2000 per trade" in contents
    assert "partial summary" not in contents
