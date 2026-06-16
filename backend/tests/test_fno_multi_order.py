"""Tests for the F&O multi-leg (spread) order path.

Covers the two pure functions at the heart of the 2026-06-16 fix:
  - `_flatten_multi_order_response` — must treat Upstox `partial_success` as a
    *partial* (placed legs exposed), NOT a total failure. Mis-classifying it as
    failure is what made the agent blind-retry a half-filled Iron Condor into a
    duplicate naked short.
  - `_marketable_limit` — spread legs must cross the spread (LTP ± buffer,
    tick-rounded) so they actually fill, instead of sitting at a passive LTP.
"""
import importlib.util
import importlib.machinery
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(BACKEND, "cli-tools")
for _p in (BACKEND, CLI):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.upstox_order_api import _flatten_multi_order_response


def _load_nf_options():
    loader = importlib.machinery.SourceFileLoader(
        "nf_options_mod", os.path.join(CLI, "nf-options")
    )
    spec = importlib.util.spec_from_loader("nf_options_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nfo = _load_nf_options()


# ---------------------------------------------------------------------------
# _flatten_multi_order_response
# ---------------------------------------------------------------------------

def test_all_success():
    resp = {
        "status": "success",
        "data": [
            {"correlation_id": "a_1", "order_id": "111"},
            {"correlation_id": "a_2", "order_id": "222"},
        ],
        "summary": {"total": 2, "payload_error": 0, "success": 2, "error": 0},
    }
    r = _flatten_multi_order_response(resp)
    assert r["success"] is True
    assert r["partial"] is False
    assert r["order_ids"] == ["111", "222"]
    assert len(r["placed"]) == 2 and not r["failed"]


def test_partial_success_is_not_total_failure():
    """The 2026-06-16 case — must surface placed legs so caller can finish/unwind."""
    resp = {
        "status": "partial_success",
        "data": [{"correlation_id": "a_1", "order_id": "111"}],
        "errors": [{"correlation_id": "a_2", "error_code": "UDAPI100500", "message": "boom"}],
        "summary": {"total": 2, "payload_error": 0, "success": 1, "error": 1},
    }
    r = _flatten_multi_order_response(resp)
    assert r["success"] is False
    assert r["partial"] is True            # <-- the critical distinction
    assert r["order_ids"] == ["111"]       # placed leg is visible, not lost
    assert len(r["placed"]) == 1
    assert r["failed"][0]["error_code"] == "UDAPI100500"


def test_total_failure():
    resp = {
        "status": "error",
        "errors": [
            {"correlation_id": "a_1", "error_code": "UDAPI1", "message": "x"},
            {"correlation_id": "a_2", "error_code": "UDAPI2", "message": "y"},
        ],
        "summary": {"total": 2, "payload_error": 0, "success": 0, "error": 2},
    }
    r = _flatten_multi_order_response(resp)
    assert r["success"] is False
    assert r["partial"] is False
    assert r["order_ids"] == []
    assert len(r["failed"]) == 2


def test_payload_error_blocks_success():
    resp = {
        "status": "success",
        "data": [{"correlation_id": "a_1", "order_id": "111"}],
        "summary": {"total": 2, "payload_error": 1, "success": 1, "error": 0},
    }
    r = _flatten_multi_order_response(resp)
    assert r["success"] is False  # a payload-rejected leg means the basket is incomplete


def test_errorCode_camelcase_fallback():
    resp = {
        "status": "partial_success",
        "data": [{"correlation_id": "a_1", "order_id": "111"}],
        "errors": [{"correlation_id": "a_2", "errorCode": "UDAPI9", "message": "z"}],
        "summary": {"total": 2, "payload_error": 0, "success": 1, "error": 1},
    }
    r = _flatten_multi_order_response(resp)
    assert r["failed"][0]["error_code"] == "UDAPI9"


def test_data_as_single_dict():
    resp = {
        "status": "success",
        "data": {"correlation_id": "a_1", "order_id": "111"},
        "summary": {"total": 1, "success": 1, "error": 0, "payload_error": 0},
    }
    r = _flatten_multi_order_response(resp)
    assert r["success"] is True
    assert r["order_ids"] == ["111"]


# ---------------------------------------------------------------------------
# _marketable_limit
# ---------------------------------------------------------------------------

def test_buy_crosses_above_ltp():
    assert nfo._marketable_limit("BUY", 100.0) > 100.0


def test_sell_crosses_below_ltp():
    assert nfo._marketable_limit("SELL", 100.0) < 100.0


def test_buy_rounds_up_to_tick():
    # 72 * 1.025 = 73.8 → already on a 0.05 tick
    assert nfo._marketable_limit("BUY", 72.0) == pytest.approx(73.80)


def test_sell_rounds_down_to_tick():
    # 80 * 0.975 = 78.0 → on tick
    assert nfo._marketable_limit("SELL", 80.0) == pytest.approx(78.00)


@pytest.mark.parametrize("side,ltp", [
    ("BUY", 12.3), ("SELL", 47.67), ("BUY", 103.42), ("SELL", 5.0), ("BUY", 0.95),
])
def test_result_is_tick_aligned(side, ltp):
    px = nfo._marketable_limit(side, ltp)
    assert abs(px / 0.05 - round(px / 0.05)) < 1e-6


def test_zero_or_missing_ltp_is_safe():
    assert nfo._marketable_limit("BUY", 0) == 0
    assert nfo._marketable_limit("SELL", None) == 0


# ---------------------------------------------------------------------------
# Regression: multi-place body MUST be a raw array, not {"orders": [...]}.
# Wrapping it returns UDAPI100036 "Invalid input" — verified against the Upstox
# sandbox 2026-06-16. The wrapper meant spread placement never worked at all.
# ---------------------------------------------------------------------------

def test_multi_place_posts_raw_array_not_wrapped(monkeypatch):
    import asyncio
    from services.upstox_order_api import AsyncUpstoxOrderApi

    captured = {}

    async def fake_call(self, method, host, path, *, params=None, json=None, timeout=None):
        captured["json"] = json
        captured["path"] = path
        return {"status": "success", "data": [],
                "summary": {"total": 0, "success": 0, "error": 0, "payload_error": 0}}

    monkeypatch.setattr(AsyncUpstoxOrderApi, "_call", fake_call)
    api = AsyncUpstoxOrderApi("tok")
    asyncio.run(api.place_multi_order([{"a": 1}, {"b": 2}]))

    assert isinstance(captured["json"], list), "body must be a raw array, not a dict"
    assert captured["json"] == [{"a": 1}, {"b": 2}]
    assert captured["path"].endswith("/multi/place")
