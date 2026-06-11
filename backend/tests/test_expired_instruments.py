"""Tests for services.expired_instruments.

respx is not installed in this venv, so we monkeypatch httpx.AsyncClient with a
small fake that records calls and returns scripted responses. The cache dir is
repointed at tmp_path via the module-level CACHE_DIR so tests never touch the
real .cache/ directory.
"""
from __future__ import annotations

import pytest

import services.expired_instruments as ei


# --------------------------------------------------------------------------- #
# Fake httpx
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, headers=None):
        self.status_code = status_code
        self._json = json_body if json_body is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(self.status_code),
            )


class _FakeAsyncClient:
    """Drop-in for httpx.AsyncClient. `script` is a list of _FakeResponse (or
    callables) consumed in order; `calls` records (url, params)."""

    script: list = []
    calls: list = []
    sleep_calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, headers=None):
        _FakeAsyncClient.calls.append((url, params))
        item = _FakeAsyncClient.script.pop(0)
        if callable(item):
            return item()
        return item


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Repoint cache at tmp_path and reset the fake client between tests."""
    monkeypatch.setattr(ei, "CACHE_DIR", tmp_path / "cache")
    _FakeAsyncClient.script = []
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.sleep_calls = []
    monkeypatch.setattr(ei.httpx, "AsyncClient", _FakeAsyncClient)

    async def _fake_sleep(secs):
        _FakeAsyncClient.sleep_calls.append(secs)

    monkeypatch.setattr(ei.asyncio, "sleep", _fake_sleep)
    yield


# --------------------------------------------------------------------------- #
# front_expiry_for_date — pure function
# --------------------------------------------------------------------------- #
def test_front_expiry_before_first():
    expiries = ["2026-05-05", "2026-05-12", "2026-05-26"]
    assert ei.front_expiry_for_date("2026-05-01", expiries) == "2026-05-05"


def test_front_expiry_between():
    expiries = ["2026-05-05", "2026-05-12", "2026-05-26"]
    assert ei.front_expiry_for_date("2026-05-06", expiries) == "2026-05-12"


def test_front_expiry_exact_match():
    expiries = ["2026-05-05", "2026-05-12", "2026-05-26"]
    assert ei.front_expiry_for_date("2026-05-12", expiries) == "2026-05-12"


def test_front_expiry_after_last_is_none():
    expiries = ["2026-05-05", "2026-05-12", "2026-05-26"]
    assert ei.front_expiry_for_date("2026-06-01", expiries) is None


def test_front_expiry_empty_list():
    assert ei.front_expiry_for_date("2026-05-01", []) is None


# --------------------------------------------------------------------------- #
# underlying_instrument_key
# --------------------------------------------------------------------------- #
def test_underlying_key_index():
    assert ei.underlying_instrument_key("nifty") == "NSE_INDEX|Nifty 50"
    assert ei.underlying_instrument_key("BANKEX") == "BSE_INDEX|BANKEX"


def test_underlying_key_equity_fallback(monkeypatch):
    import services.instruments_cache as ic

    monkeypatch.setattr(ic, "get_instrument_key", lambda s: "NSE_EQ|INE001A01036")
    assert ei.underlying_instrument_key("RELIANCE") == "NSE_EQ|INE001A01036"


def test_underlying_key_unresolvable_raises(monkeypatch):
    import services.instruments_cache as ic

    monkeypatch.setattr(ic, "get_instrument_key", lambda s: None)
    with pytest.raises(ValueError):
        ei.underlying_instrument_key("NOTAREALSYMBOL")


# --------------------------------------------------------------------------- #
# fetch_expired_candles — reversal + permanent caching
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_candles_reversed_to_ascending():
    # Upstox returns newest-first.
    _FakeAsyncClient.script = [
        _FakeResponse(
            json_body={
                "data": {
                    "candles": [
                        ["2026-05-26T15:29:00+05:30", 110, 112, 109, 111, 500, 1200],
                        ["2026-05-26T15:28:00+05:30", 108, 111, 107, 110, 400, 1180],
                        ["2026-05-26T15:27:00+05:30", 105, 109, 104, 108, 300, 1150],
                    ]
                }
            }
        )
    ]
    out = await ei.fetch_expired_candles(
        "tok", "NSE_FO|72172|26-05-2026", "1minute", "2026-05-26", "2026-05-26"
    )
    ts = [c["timestamp"] for c in out]
    assert ts == [
        "2026-05-26T15:27:00+05:30",
        "2026-05-26T15:28:00+05:30",
        "2026-05-26T15:29:00+05:30",
    ]
    # field typing
    assert out[0]["open"] == 105.0 and isinstance(out[0]["open"], float)
    assert out[0]["oi"] == 1150.0
    assert out[-1]["close"] == 111.0


@pytest.mark.asyncio
async def test_candles_permanent_cache_no_second_http():
    _FakeAsyncClient.script = [
        _FakeResponse(
            json_body={"data": {"candles": [["t1", 1, 2, 0, 1, 10, 5]]}}
        )
    ]
    first = await ei.fetch_expired_candles(
        "tok", "NSE_FO|9|26-05-2026", "5minute", "2026-05-20", "2026-05-26"
    )
    assert len(_FakeAsyncClient.calls) == 1
    # No more scripted responses; a second HTTP call would IndexError.
    second = await ei.fetch_expired_candles(
        "tok", "NSE_FO|9|26-05-2026", "5minute", "2026-05-20", "2026-05-26"
    )
    assert first == second
    assert len(_FakeAsyncClient.calls) == 1  # served from disk cache


@pytest.mark.asyncio
async def test_candles_url_encodes_pipe():
    _FakeAsyncClient.script = [_FakeResponse(json_body={"data": {"candles": []}})]
    await ei.fetch_expired_candles(
        "tok", "NSE_FO|72172|26-05-2026", "day", "2026-05-01", "2026-05-26"
    )
    url, _params = _FakeAsyncClient.calls[0]
    assert "%7C" in url
    assert "|" not in url


# --------------------------------------------------------------------------- #
# get_expired_contracts — past cached, future not cached
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_contracts_past_cached(monkeypatch):
    monkeypatch.setattr(ei, "_today_iso", lambda: "2026-06-11")
    _FakeAsyncClient.script = [
        _FakeResponse(json_body={"data": [{"instrument_key": "NSE_FO|1|26-05-2026"}]})
    ]
    first = await ei.get_expired_contracts("tok", "NIFTY", "2026-05-26")
    assert first == [{"instrument_key": "NSE_FO|1|26-05-2026"}]
    assert len(_FakeAsyncClient.calls) == 1
    # second call served from cache (no scripted response left)
    second = await ei.get_expired_contracts("tok", "NIFTY", "2026-05-26")
    assert second == first
    assert len(_FakeAsyncClient.calls) == 1


@pytest.mark.asyncio
async def test_contracts_future_not_cached(monkeypatch):
    monkeypatch.setattr(ei, "_today_iso", lambda: "2026-06-11")
    _FakeAsyncClient.script = [
        _FakeResponse(json_body={"data": [{"instrument_key": "fut1"}]}),
        _FakeResponse(json_body={"data": [{"instrument_key": "fut2"}]}),
    ]
    a = await ei.get_expired_contracts("tok", "NIFTY", "2026-06-30")
    b = await ei.get_expired_contracts("tok", "NIFTY", "2026-06-30")
    # both hit HTTP (future expiry is not cached)
    assert len(_FakeAsyncClient.calls) == 2
    assert a == [{"instrument_key": "fut1"}]
    assert b == [{"instrument_key": "fut2"}]


# --------------------------------------------------------------------------- #
# get_expiries — sorted + TTL cache
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_expiries_sorted_and_cached():
    _FakeAsyncClient.script = [
        _FakeResponse(json_body={"data": ["2026-05-26", "2026-05-05", "2026-05-12"]})
    ]
    out = await ei.get_expiries("tok", "NIFTY")
    assert out == ["2026-05-05", "2026-05-12", "2026-05-26"]
    # fresh cache → second call served from disk
    again = await ei.get_expiries("tok", "NIFTY")
    assert again == out
    assert len(_FakeAsyncClient.calls) == 1


# --------------------------------------------------------------------------- #
# 429 retry then success
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_429_retry_then_success():
    _FakeAsyncClient.script = [
        _FakeResponse(status_code=429, headers={"Retry-After": "2"}),
        _FakeResponse(status_code=429),  # no header → backoff schedule
        _FakeResponse(json_body={"data": ["2026-05-05"]}),
    ]
    out = await ei.get_expiries("tok", "NIFTY")
    assert out == ["2026-05-05"]
    assert len(_FakeAsyncClient.calls) == 3
    # honored Retry-After (2s) then backoff schedule index 1 (2.0s)
    assert _FakeAsyncClient.sleep_calls == [2.0, 2.0]


@pytest.mark.asyncio
async def test_429_exhausted_raises():
    import httpx

    _FakeAsyncClient.script = [
        _FakeResponse(status_code=429),
        _FakeResponse(status_code=429),
        _FakeResponse(status_code=429),
        _FakeResponse(status_code=429),
    ]
    with pytest.raises(httpx.HTTPStatusError):
        await ei.get_expiries("tok", "NIFTY")


# --------------------------------------------------------------------------- #
# cache corruption fallback
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_corrupt_cache_falls_back_to_refetch():
    # First populate a valid cache.
    _FakeAsyncClient.script = [
        _FakeResponse(json_body={"data": {"candles": [["t1", 1, 2, 0, 1, 10, 5]]}})
    ]
    await ei.fetch_expired_candles("tok", "NSE_FO|9|26-05-2026", "1minute", "2026-05-26", "2026-05-26")
    fname = ei._safe_filename(
        "candles", "NSE_FO|9|26-05-2026", "1minute", "2026-05-26", "2026-05-26"
    )
    path = ei._cache_path(fname)
    # Corrupt the file.
    path.write_text("{ this is not valid json", encoding="utf-8")

    # Next call must ignore the corrupt cache and refetch.
    _FakeAsyncClient.script = [
        _FakeResponse(json_body={"data": {"candles": [["t2", 2, 3, 1, 2, 20, 6]]}})
    ]
    out = await ei.fetch_expired_candles(
        "tok", "NSE_FO|9|26-05-2026", "1minute", "2026-05-26", "2026-05-26"
    )
    assert out[0]["timestamp"] == "t2"
