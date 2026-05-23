"""Phase 1 tests — curated user-profile capability + synthesis job.

See docs/plans/2026-05-23-prefix-cache-memory-port.md.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.capabilities import UserProfileCapability  # noqa: E402
from agents.capabilities.context_injection import MemoryCapability  # noqa: E402


def _ctx(profile):
    """Minimal stand-in for RunContext — build() only reads ctx.deps.user_profile."""
    return SimpleNamespace(deps=SimpleNamespace(user_profile=profile))


def test_profile_injected_when_present():
    build = UserProfileCapability().get_instructions()
    out = build(_ctx("Experienced intraday trader. Prefers EMA-cross entries. Avoids penny stocks."))
    assert "## USER PROFILE (Auto-synthesized)" in out
    assert "EMA-cross" in out
    assert "personalize your assistance" in out


def test_profile_empty_when_absent():
    build = UserProfileCapability().get_instructions()
    assert build(_ctx(None)) == ""
    assert build(_ctx("")) == ""


def test_profile_byte_stable_across_turns():
    """Frozen content MUST be byte-identical turn-over-turn or the prefix cache
    breaks for everything after it (advisor's hidden-cliff). Same deps -> same bytes."""
    build = UserProfileCapability().get_instructions()
    profile = "Risk: moderate. Capital ₹5L. Trades BANKNIFTY weekly options."
    a = build(_ctx(profile))
    b = build(_ctx(profile))
    assert a == b
    # And a fresh capability instance must produce identical bytes too.
    c = UserProfileCapability().get_instructions()(_ctx(profile))
    assert a == c


def test_profile_distinct_from_memory_block():
    """UserProfile (frozen) and Memory (volatile recall) are different sections.

    Memory is suppressed from instructions under the default-on prefix-cache
    layout, so use is_awakening=True (layout off) to see it emit here.
    """
    prof = UserProfileCapability().get_instructions()(_ctx("X"))
    mem = MemoryCapability().get_instructions()(
        SimpleNamespace(deps=SimpleNamespace(user_memories=["m1"], is_awakening=True))
    )
    assert "USER PROFILE" in prof
    assert "REMEMBERED INFORMATION" in mem
    assert prof != mem


def test_deps_has_user_profile_field():
    from agents.orchestrator import OrchestratorDeps
    assert "user_profile" in OrchestratorDeps.model_fields


def test_job_extract_json_variants():
    from jobs.memory_profile import _extract_json
    payload = '{"profile": {"risk_tolerance": "low"}, "profile_text": "Cautious trader."}'
    # raw
    assert _extract_json(payload)["profile_text"] == "Cautious trader."
    # fenced
    assert _extract_json(f"```json\n{payload}\n```")["profile"]["risk_tolerance"] == "low"
    # with preamble noise + braces
    assert _extract_json(f"Here you go:\n{payload}\nDone.")["profile_text"] == "Cautious trader."
    # garbage -> {}
    assert _extract_json("no json here") == {}
    assert _extract_json("") == {}
