"""Snapshot must not flag signal-session-held positions as UNPROTECTED.

A scalp/signal session exits its position on an indicator flip, not via a
price-based monitor rule. Before this fix the trading snapshot only looked at
monitor rules, so daemon-managed scalp positions (equity and options) were
falsely flagged "⚠ UNPROTECTED" — which spooked the agent into manual exits
(daily thread daily_1_2026-06-04, NS feedback). The check must consult active
scalp sessions BEFORE declaring a missing SL.
"""
from types import SimpleNamespace

from services.trading_snapshot import _is_holding, _scalp_symbol_map


def _sess(sid, underlying, *, enabled=True, state="HOLDING_LONG", indicator="supertrend",
          entry_side="long", current_tradingsymbol=None, current_instrument_token=None):
    return SimpleNamespace(
        id=sid, underlying=underlying, current_tradingsymbol=current_tradingsymbol,
        current_instrument_token=current_instrument_token,
        enabled=enabled, state=state, primary_indicator=indicator, entry_side=entry_side,
    )


def test_equity_underlying_mapped():
    m = _scalp_symbol_map([_sess(128, "GESHIP"), _sess(130, "TATACOMM")])
    assert m["GESHIP"].id == 128
    assert m["TATACOMM"].id == 130


def test_symbol_match_is_case_insensitive():
    m = _scalp_symbol_map([_sess(88, "induSINDbk")])
    assert "INDUSINDBK" in m


def test_option_contract_mapped_by_tradingsymbol():
    s = _sess(95, "NIFTY", indicator="qqe_mod",
              current_tradingsymbol="NIFTY24JUN23450CE")
    m = _scalp_symbol_map([s])
    assert "NIFTY24JUN23450CE" in m
    assert m["NIFTY24JUN23450CE"].id == 95


def test_missing_fields_dont_crash():
    s = SimpleNamespace(id=1, underlying=None, current_tradingsymbol=None,
                        current_instrument_token=None, state="HOLDING_LONG")
    assert _scalp_symbol_map([s]) == {}


def test_first_session_wins_on_tie():
    m = _scalp_symbol_map([_sess(1, "SBIN"), _sess(2, "SBIN")])
    assert m["SBIN"].id == 1


# --- holding-state gate: an IDLE/flat session must NOT mask a naked position ---

def test_idle_session_is_not_holding():
    assert _is_holding(_sess(1, "SBIN", state="IDLE")) is False


def test_all_holding_states_count():
    for st in ("HOLDING_LONG", "HOLDING_SHORT", "HOLDING_CE", "HOLDING_PE"):
        assert _is_holding(_sess(1, "X", state=st)) is True


def test_idle_session_excluded_from_map():
    """Enabled-but-flat session over a held symbol → NOT treated as managing it."""
    m = _scalp_symbol_map([_sess(128, "GESHIP", state="IDLE")])
    assert m == {}
    # ...so the position is still correctly flagged unprotected:
    assert _is_unprotected("GESHIP", has_rule_protector=False, scalp_map=m) is True


# --- instrument-token match (options whose display symbol differs) ------------

def test_option_matched_by_instrument_token():
    s = _sess(95, "NIFTY", state="HOLDING_CE", indicator="qqe_mod",
              current_tradingsymbol="NIFTY24JUN23450CE",
              current_instrument_token="NSE_FO|45678")
    m = _scalp_symbol_map([s])
    # The position's displayed symbol ("NIFTY 23450CE") won't string-match, but
    # the broker instrument token will.
    assert m.get("NSE_FO|45678") is s


# --- the gating decision the snapshot loop performs ---------------------------

def _is_unprotected(symbol, has_rule_protector, scalp_map):
    """Mirror of the snapshot's gate: unprotected iff no monitor protector AND
    no managing scalp session."""
    sess = scalp_map.get(symbol.upper())
    return (not has_rule_protector) and (sess is None)


def test_signal_managed_without_rule_is_not_unprotected():
    m = _scalp_symbol_map([_sess(128, "GESHIP")])
    # No price-based SL rule, but a signal session manages it.
    assert _is_unprotected("GESHIP", has_rule_protector=False, scalp_map=m) is False


def test_truly_orphan_position_is_still_unprotected():
    m = _scalp_symbol_map([_sess(128, "GESHIP")])
    # A held name with neither a rule nor a session is genuinely unprotected.
    assert _is_unprotected("VOLTAS", has_rule_protector=False, scalp_map=m) is True


def test_rule_protected_position_is_not_unprotected():
    assert _is_unprotected("VOLTAS", has_rule_protector=True, scalp_map={}) is False
