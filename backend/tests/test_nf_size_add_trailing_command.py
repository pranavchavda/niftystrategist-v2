"""Tests for nf-size --atr-trail emitting a ready-to-paste `nf-monitor
add-trailing` command (cli-tools/nf-size:_build_add_trailing_command).

The command collapses "run nf-size → copy a width → separately stamp
provenance" into one paste. Pasting as-is yields COMPLETE width_provenance
(tuned=false); tuning means editing ONLY --trail-percent while --baseline-trail
stays as the anchor (tuned=true, baseline preserved). This is the fix for the
Post-Close audit's false positive (a good trail flagged because provenance was
never stamped).

Built 2026-06-27 (Pranav approved 2026-06-24). See project_trail_only_stops.md.
"""
import importlib.machinery
import importlib.util
import os
import shlex
import sys

import pytest

_CLI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli-tools")
if _CLI_DIR not in sys.path:
    sys.path.insert(0, _CLI_DIR)


@pytest.fixture(scope="module")
def nfsize():
    loader = importlib.machinery.SourceFileLoader("nfsize", os.path.join(_CLI_DIR, "nf-size"))
    spec = importlib.util.spec_from_loader("nfsize", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nfsize"] = mod
    loader.exec_module(mod)
    return mod


def _result(**overrides):
    """A representative --atr-trail result dict (the shape size_atr_trail returns)."""
    base = {
        "kind": "equity_atr_trail",
        "symbol": "KPRMILL",
        "direction": "long",
        "product": "I",
        "trail_percent": 3.2,
        "recommended_qty": 120,
        "atr_14": 18.45,
        "k": 2.75,
        "regime": "trending",
    }
    base.update(overrides)
    return base


def _flags(cmd: str) -> dict:
    """Parse the emitted command into a {flag: value} map (drops the leading
    `nf-monitor add-trailing`)."""
    toks = shlex.split(cmd)
    assert toks[:2] == ["nf-monitor", "add-trailing"]
    rest = toks[2:]
    out = {}
    i = 0
    while i < len(rest):
        assert rest[i].startswith("--"), f"expected a flag at {rest[i]!r}"
        out[rest[i]] = rest[i + 1]
        i += 2
    return out


# ── core mapping ─────────────────────────────────────────────────────────────

def test_long_maps_to_sell_exit(nfsize):
    cmd = nfsize._build_add_trailing_command(_result(direction="long"))
    assert _flags(cmd)["--side"] == "SELL"


def test_short_maps_to_buy_exit(nfsize):
    cmd = nfsize._build_add_trailing_command(_result(direction="short"))
    assert _flags(cmd)["--side"] == "BUY"


def test_qty_and_symbol_and_product_carried(nfsize):
    f = _flags(nfsize._build_add_trailing_command(_result(symbol="KPRMILL", recommended_qty=120, product="D")))
    assert f["--symbol"] == "KPRMILL"
    assert f["--qty"] == "120"
    assert f["--product"] == "D"


def test_product_defaults_to_intraday_when_missing(nfsize):
    f = _flags(nfsize._build_add_trailing_command(_result(product=None)))
    assert f["--product"] == "I"


# ── provenance is always pre-filled (the whole point) ────────────────────────

def test_provenance_flags_all_present(nfsize):
    f = _flags(nfsize._build_add_trailing_command(_result()))
    for flag in ("--atr", "--k", "--regime", "--baseline-trail"):
        assert flag in f, f"missing provenance flag {flag}"


def test_baseline_equals_trail_so_paste_as_is_is_untuned(nfsize):
    # --trail-percent and --baseline-trail start equal → cmd_add_trailing
    # computes tuned=false. Editing ONLY --trail-percent later flips it true.
    f = _flags(nfsize._build_add_trailing_command(_result(trail_percent=3.2)))
    assert f["--trail-percent"] == f["--baseline-trail"] == "3.2"


def test_provenance_values_come_from_the_computation(nfsize):
    f = _flags(nfsize._build_add_trailing_command(_result(atr_14=18.45, k=2.75, regime="trending")))
    assert f["--atr"] == "18.45"
    assert f["--k"] == "2.75"
    assert f["--regime"] == "trending"


# ── no qty → no command (caller surfaces a warning instead) ──────────────────

@pytest.mark.parametrize("qty", [0, None])
def test_zero_or_missing_qty_returns_none(nfsize, qty):
    assert nfsize._build_add_trailing_command(_result(recommended_qty=qty)) is None


# ── drift guard: every emitted flag must exist in nf-monitor add-trailing ────

def test_every_emitted_flag_is_accepted_by_nf_monitor(nfsize):
    """Ties the emitter to its consumer without duplicating the parser: assert
    each flag the command emits is declared in nf-monitor's source. If someone
    renames a flag in nf-monitor, this fails."""
    cmd = nfsize._build_add_trailing_command(_result())
    with open(os.path.join(_CLI_DIR, "nf-monitor"), encoding="utf-8") as fh:
        monitor_src = fh.read()
    for flag in _flags(cmd):
        assert f'"{flag}"' in monitor_src, f"{flag} not declared in nf-monitor add-trailing parser"
