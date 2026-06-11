"""Tests for rolling-expiry options-scalp wiring in the backtest API + jobs.

All network + engine calls are monkeypatched: no Upstox, no expired-instruments
service, no real scalp engine. We assert the *plumbing* — that ``expiry=="rolling"``
(case-insensitive) triggers the expired-instruments path, computes the needed
front-of-book expiries from the replay window (incl. the current-week live-cache
fallback), routes expired-format leg keys to ``fetch_expired_candles`` and plain
keys to the live fetch, fails cleanly on a missing token, and that non-rolling
requests take the exact old path (no expired-service calls).

The parallel engine/service agents own ``backtesting/scalp_options.py`` and
``services/expired_instruments.py``; we don't depend on their internals here —
everything they expose is monkeypatched at the ``api.backtest`` call sites.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException

import api.backtest as bt
from auth import User
from api.backtest import ScalpBacktestRequest


# --------------------------------------------------------------------------- #
# Lightweight fakes
# --------------------------------------------------------------------------- #


@dataclass
class _FakeCandle:
    timestamp: str
    open: float = 100.0
    high: float = 101.0
    low: float = 99.0
    close: float = 100.0
    volume: float = 0.0


@dataclass
class _FakePlan:
    date: str
    strike: float
    option_type: str
    instrument_key: str
    tradingsymbol: str = ""
    expiry: str | None = None
    lot_size: int = 50


@dataclass
class _FakeResult:
    """Stand-in for ScalpOptionsBacktestResult — only the fields the
    serializer reads."""
    underlying: str = "NIFTY"
    expiry: str = "rolling"
    interval: str = "5minute"
    days: int = 30
    config: dict = field(default_factory=lambda: {"lots": 1})
    candle_count: int = 0
    session_days: int = 0
    trades: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    metrics_net: dict = field(default_factory=dict)
    charges_total: float = 0.0
    slippage_total: float = 0.0
    intra_bar_ambiguity: int = 0
    primary_flips: int = 0
    confirm_blocks: int = 0
    cooldown_blocks: int = 0
    max_trades_blocks: int = 0
    squareoff_exits: int = 0
    missing_leg_blocks: int = 0
    no_strike_blocks: int = 0
    post_cutoff_blocks: int = 0
    entry_side_blocks: int = 0
    expiries_used: list = field(default_factory=lambda: ["2026-05-29", "2026-06-05"])


class _FakeClient:
    """get_market_data_client / UpstoxClient stand-in. Records live
    get_historical_data calls so tests can assert routing."""

    def __init__(self) -> None:
        self.live_fetches: list[str] = []
        # Two days post-warmup; warmup prefix of 1 candle.
        self._candles = [
            _FakeCandle("2026-05-28T09:15:00+05:30"),   # warmup
            _FakeCandle("2026-05-29T09:15:00+05:30"),   # day 1
            _FakeCandle("2026-06-05T09:15:00+05:30"),   # day 2
        ]

    async def get_historical_data(self, *args, **kwargs):
        ik = kwargs.get("instrument_key")
        if ik:
            self.live_fetches.append(ik)
            return [_FakeCandle("2026-06-05T09:20:00+05:30")]
        return list(self._candles)


def _user() -> User:
    return User(id=42, email="t@example.com", name="T", permissions=[])


@pytest.fixture
def patched(monkeypatch):
    """Patch the underlying-candle fetch + engine to deterministic fakes.

    Returns a namespace recording what the expired-instruments service was
    asked to do so individual tests can assert against it.
    """
    client = _FakeClient()

    async def fake_get_market_data_client(user):
        return client

    # fetch_with_warmup returns (ohlcv, warmup_bars=1)
    async def fake_fetch_with_warmup(c, underlying, interval, days, instrument_key=None):
        return list(client._candles), 1

    monkeypatch.setattr("api.cockpit.get_market_data_client", fake_get_market_data_client)
    monkeypatch.setattr(bt, "fetch_with_warmup", fake_fetch_with_warmup)

    # Engine: plan returns one expired-format leg + one live-format leg.
    plans = [
        _FakePlan("2026-05-29", 25000.0, "CE",
                  "NSE_FO|72172|29-05-2026", expiry="2026-05-29"),
        _FakePlan("2026-06-05", 25100.0, "PE",
                  "NSE_FO|88888", expiry="2026-06-05"),
    ]

    def fake_plan_atm_legs(candles, cfg, interval, warmup_bars, rolling=None):
        fake_plan_atm_legs.last_rolling = rolling
        return list(plans)

    fake_plan_atm_legs.last_rolling = "UNSET"

    def fake_run(underlying_candles, leg_candles_by_key, cfg, **kwargs):
        fake_run.last_rolling = kwargs.get("rolling")
        fake_run.last_leg_keys = set(leg_candles_by_key)
        return _FakeResult()

    fake_run.last_rolling = "UNSET"
    fake_run.last_leg_keys = set()

    monkeypatch.setattr(bt, "plan_atm_legs", fake_plan_atm_legs)
    monkeypatch.setattr(bt, "run_scalp_options_backtest", fake_run)
    # Jobs path imports these from the source module locally, so patch there too.
    monkeypatch.setattr("backtesting.scalp_options.plan_atm_legs", fake_plan_atm_legs)
    monkeypatch.setattr("backtesting.scalp_options.run_scalp_options_backtest", fake_run)

    # expired-instruments service
    calls = {"get_expiries": 0, "get_expired_contracts": [], "fetch_expired_candles": []}

    async def fake_get_expiries(token, underlying):
        calls["get_expiries"] += 1
        # Past expiry + a current/future one so both branches of needed exercise.
        return ["2026-05-29", "2026-06-05"]

    async def fake_get_expired_contracts(token, underlying, expiry):
        calls["get_expired_contracts"].append(expiry)
        return [{
            "instrument_key": "NSE_FO|72172|29-05-2026",
            "trading_symbol": "NIFTY29MAY25000CE",
            "strike_price": 25000.0,
            "instrument_type": "CE",
            "lot_size": 50,
            "expiry": expiry,
        }]

    async def fake_fetch_expired_candles(token, ik, interval, from_date, to_date):
        calls["fetch_expired_candles"].append((ik, from_date, to_date))
        return [{
            "timestamp": "2026-05-29T09:20:00+05:30",
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
            "volume": 0.0, "oi": 0.0,
        }]

    def fake_front_expiry_for_date(d, expiries):
        cands = [e for e in expiries if e >= d]
        return min(cands) if cands else None

    def fake_today_iso():
        # 2026-05-29 is past; 2026-06-05 is "today-or-later" → live-cache branch.
        return "2026-06-01"

    monkeypatch.setattr("services.expired_instruments.get_expiries", fake_get_expiries)
    monkeypatch.setattr("services.expired_instruments.get_expired_contracts",
                        fake_get_expired_contracts)
    monkeypatch.setattr("services.expired_instruments.fetch_expired_candles",
                        fake_fetch_expired_candles)
    monkeypatch.setattr("services.expired_instruments.front_expiry_for_date",
                        fake_front_expiry_for_date)
    monkeypatch.setattr("services.expired_instruments._today_iso", fake_today_iso)

    # live-cache fallback for the current-week front weekly
    live_cache_calls = []

    def fake_live_cache_contracts(underlying, expiry):
        live_cache_calls.append((underlying, expiry))
        return [{
            "instrument_key": "NSE_FO|88888",
            "trading_symbol": "NIFTY05JUN25100PE",
            "strike_price": 25100.0,
            "instrument_type": "PE",
            "lot_size": 50,
            "expiry": expiry,
        }]

    monkeypatch.setattr(bt, "_live_cache_contracts", fake_live_cache_contracts)

    # token (for rolling)
    async def fake_token(user_id, *a, **k):
        return "TOK"

    monkeypatch.setattr("api.upstox_oauth.get_user_upstox_token", fake_token)

    class NS:
        pass

    ns = NS()
    ns.client = client
    ns.calls = calls
    ns.live_cache_calls = live_cache_calls
    ns.plan_fn = fake_plan_atm_legs
    ns.run_fn = fake_run
    return ns


def _rolling_body() -> ScalpBacktestRequest:
    return ScalpBacktestRequest(
        underlying="NIFTY",
        expiry="rolling",
        lots=1,
        days=30,
        interval="5minute",
        session_mode="options_scalp",
        primary_indicator="utbot",
    )


# --------------------------------------------------------------------------- #
# (a) rolling triggers expiries fetch + needed-expiry computation + live fallback
# --------------------------------------------------------------------------- #


def test_rolling_triggers_expiry_fetch_and_needed_computation(patched):
    out = asyncio.run(bt._run_options_scalp_sync(_rolling_body(), _user()))

    # get_expiries called exactly once
    assert patched.calls["get_expiries"] == 1

    # Replay window has two dates → both front expiries needed.
    # 2026-05-29 is past → expired-contracts; 2026-06-05 >= today → live cache.
    assert patched.calls["get_expired_contracts"] == ["2026-05-29"]
    assert patched.live_cache_calls == [("NIFTY", "2026-06-05")]

    # RollingExpiryData was threaded into both engine entry points.
    rolling = patched.plan_fn.last_rolling
    assert rolling is not None
    assert sorted(rolling.expiries) == ["2026-05-29", "2026-06-05"]
    assert set(rolling.contracts_by_expiry) == {"2026-05-29", "2026-06-05"}
    assert patched.run_fn.last_rolling is rolling

    # Serialized result carries expiries_used at top level.
    assert out["expiries_used"] == ["2026-05-29", "2026-06-05"]


def test_rolling_sentinel_is_case_insensitive(patched):
    body = _rolling_body()
    body.expiry = "ROLLING"
    out = asyncio.run(bt._run_options_scalp_sync(body, _user()))
    assert patched.calls["get_expiries"] == 1
    assert out["expiries_used"]


# --------------------------------------------------------------------------- #
# (b) leg routing — expired-format key → fetch_expired_candles, plain → live
# --------------------------------------------------------------------------- #


def test_leg_key_routing(patched):
    asyncio.run(bt._run_options_scalp_sync(_rolling_body(), _user()))

    # Expired-format key (two pipes + date) went to fetch_expired_candles.
    expired_keys = [c[0] for c in patched.calls["fetch_expired_candles"]]
    assert expired_keys == ["NSE_FO|72172|29-05-2026"]
    # from_date clamped to window start (first tradable date), to_date = expiry.
    _ik, from_date, to_date = patched.calls["fetch_expired_candles"][0]
    assert from_date == "2026-05-29"          # window start
    assert to_date == "2026-05-29"            # leg expiry

    # Plain live-format key went through the live get_historical_data path.
    assert patched.client.live_fetches == ["NSE_FO|88888"]

    # Both legs ended up in the engine's leg-candle map.
    assert patched.run_fn.last_leg_keys == {"NSE_FO|72172|29-05-2026", "NSE_FO|88888"}


def test_is_expired_instrument_key():
    assert bt._is_expired_instrument_key("NSE_FO|72172|29-05-2026")
    assert not bt._is_expired_instrument_key("NSE_FO|88888")
    assert not bt._is_expired_instrument_key("NSE_EQ|INE002A01018")


# --------------------------------------------------------------------------- #
# (c) missing token → clean 400
# --------------------------------------------------------------------------- #


def test_rolling_missing_token_400(patched, monkeypatch):
    async def no_token(user_id, *a, **k):
        return None

    monkeypatch.setattr("api.upstox_oauth.get_user_upstox_token", no_token)

    with pytest.raises(HTTPException) as ei:
        asyncio.run(bt._run_options_scalp_sync(_rolling_body(), _user()))
    assert ei.value.status_code == 400
    assert "Plus plan" in ei.value.detail
    # Never reached the expired-instruments service.
    assert patched.calls["get_expiries"] == 0


# --------------------------------------------------------------------------- #
# (d) non-rolling takes the exact old path — no expired-service calls
# --------------------------------------------------------------------------- #


def test_non_rolling_skips_expired_service(patched):
    body = _rolling_body()
    body.expiry = "2026-06-05"   # fixed ISO expiry

    out = asyncio.run(bt._run_options_scalp_sync(body, _user()))

    # No expired-instruments service involvement whatsoever.
    assert patched.calls["get_expiries"] == 0
    assert patched.calls["get_expired_contracts"] == []
    assert patched.calls["fetch_expired_candles"] == []
    assert patched.live_cache_calls == []

    # plan + run were called with rolling=None (old path).
    assert patched.plan_fn.last_rolling is None
    assert patched.run_fn.last_rolling is None

    # All legs fetched via the live path (both planned keys), since non-rolling
    # ignores key format and always uses get_historical_data.
    assert set(patched.client.live_fetches) == {"NSE_FO|72172|29-05-2026", "NSE_FO|88888"}

    # Still serializes expiries_used (from the fake result).
    assert out["expiries_used"] == ["2026-05-29", "2026-06-05"]


# --------------------------------------------------------------------------- #
# Jobs path mirror — rolling wiring through services.backtest_jobs
# --------------------------------------------------------------------------- #


def test_jobs_path_rolling(patched, monkeypatch):
    import services.backtest_jobs as jobs

    # Jobs path constructs its own UpstoxClient — patch it to our fake client.
    monkeypatch.setattr("services.upstox_client.UpstoxClient",
                        lambda *a, **k: patched.client)

    # Jobs token + progress are async no-ops / fixed.
    async def fake_token(user_id, *a, **k):
        return "TOK"

    monkeypatch.setattr("api.upstox_oauth.get_user_upstox_token", fake_token)

    async def fake_progress(*a, **k):
        return None

    async def fake_check_cancel(job_id):
        return False

    monkeypatch.setattr(jobs, "_update_progress", fake_progress)
    monkeypatch.setattr(jobs, "_check_cancel", fake_check_cancel)

    config = {
        "underlying": "NIFTY",
        "expiry": "rolling",
        "lots": 1,
        "days": 30,
        "interval": "5minute",
        "session_mode": "options_scalp",
        "primary_indicator": "utbot",
    }

    out = asyncio.run(jobs._run_scalp_options(job_id=1, user_id=42, config=config))

    assert patched.calls["get_expiries"] == 1
    assert patched.calls["get_expired_contracts"] == ["2026-05-29"]
    assert patched.live_cache_calls == [("NIFTY", "2026-06-05")]
    assert patched.run_fn.last_rolling is not None
    assert out["expiries_used"] == ["2026-05-29", "2026-06-05"]


def test_jobs_path_non_rolling_skips_expired_service(patched, monkeypatch):
    import services.backtest_jobs as jobs

    monkeypatch.setattr("services.upstox_client.UpstoxClient",
                        lambda *a, **k: patched.client)

    async def fake_token(user_id, *a, **k):
        return "TOK"

    monkeypatch.setattr("api.upstox_oauth.get_user_upstox_token", fake_token)

    async def fake_progress(*a, **k):
        return None

    async def fake_check_cancel(job_id):
        return False

    monkeypatch.setattr(jobs, "_update_progress", fake_progress)
    monkeypatch.setattr(jobs, "_check_cancel", fake_check_cancel)

    config = {
        "underlying": "NIFTY",
        "expiry": "2026-06-05",
        "lots": 1,
        "days": 30,
        "interval": "5minute",
        "session_mode": "options_scalp",
        "primary_indicator": "utbot",
    }

    asyncio.run(jobs._run_scalp_options(job_id=1, user_id=42, config=config))

    assert patched.calls["get_expiries"] == 0
    assert patched.calls["get_expired_contracts"] == []
    assert patched.calls["fetch_expired_candles"] == []
    assert patched.plan_fn.last_rolling is None
    assert patched.run_fn.last_rolling is None
