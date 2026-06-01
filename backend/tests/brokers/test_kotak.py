"""Kotak Neo adapter: instrument mapping, order-body mapping, read normalization,
and the pure-REST TOTP login flow — all against fakes (no network)."""

import pytest

from brokers.base import (
    InstrumentDescriptor,
    OrderSpec,
    OrderType,
    ProductType,
    TransactionType,
)
from brokers.kotak.account import KotakBrokerAccount
from brokers.kotak.auth import KotakAuth, KotakStore, _session_is_fresh
from brokers.kotak.instruments import KotakInstrumentResolver
from models.trading import Portfolio


# ── instrument identity ─────────────────────────────────────────────────────
def test_equity_resolves_to_es_ts_pair():
    r = KotakInstrumentResolver()
    assert r.resolve_pair(InstrumentDescriptor(symbol="RELIANCE")) == ("nse_cm", "RELIANCE-EQ")
    assert r.resolve_order_instrument(InstrumentDescriptor(symbol="TCS")) == "nse_cm:TCS-EQ"


def test_equity_round_trip():
    r = KotakInstrumentResolver()
    nid = r.resolve_order_instrument(InstrumentDescriptor(symbol="INFY"))
    back = r.to_canonical(nid)
    assert back.instrument_kind == "EQ"
    assert back.symbol == "INFY"
    assert r.resolve_order_instrument(back) == nid


def test_fno_resolution_deferred_not_silent():
    r = KotakInstrumentResolver()
    with pytest.raises(ValueError):
        r.resolve_pair(InstrumentDescriptor(instrument_kind="OPT", underlying="NIFTY"))


# ── order-body mapping ──────────────────────────────────────────────────────
def _account_capturing(captured):
    acct = KotakBrokerAccount(session={"base_url": "https://e22.x", "edit_sid": "s",
                                        "edit_token": "t", "serverId": "srv"})

    async def fake_rest(method, path, *, body=None):
        captured.append({"method": method, "path": path, "body": body})
        if path.endswith("/place"):
            return {"data": {"nOrdNo": "K12345"}}
        return {"data": []}

    acct._rest = fake_rest
    return acct


@pytest.mark.asyncio
async def test_place_order_maps_to_kotak_body():
    captured = []
    acct = _account_capturing(captured)
    spec = OrderSpec(
        transaction_type=TransactionType.SELL,
        quantity=10,
        order_type=OrderType.LIMIT,
        price=1490.0,
        symbol="RELIANCE",
        product=ProductType.INTRADAY,
    )
    result = await acct.place_order(spec)
    assert result.success and result.order_id == "K12345"
    body = captured[0]["body"]
    assert captured[0]["path"] == "/quick/order/rule/ms/place"
    assert body["es"] == "nse_cm"           # NSE equity segment
    assert body["ts"] == "RELIANCE-EQ"
    assert body["pc"] == "MIS"              # INTRADAY -> MIS
    assert body["pt"] == "L"               # LIMIT -> L
    assert body["tt"] == "S"               # SELL -> "S" (Kotak code, not "SELL")
    assert body["pr"] == "1490.0"
    assert body["qt"] == "10"


@pytest.mark.asyncio
async def test_cancel_reports_failure_on_kotak_error():
    """A rejected cancel returns {stCode, errMsg} — must surface success=False,
    not the old unconditional success=True (caught live 2026-06-01)."""
    acct = KotakBrokerAccount(session={})

    async def fake_rest(method, path, *, body=None):
        return {"stCode": 1022, "errMsg": "order is rejected",
                "stat": "please provide valid order number"}

    acct._rest = fake_rest
    r = await acct.cancel_order("260601000550944")
    assert r["success"] is False
    assert "rejected" in r["message"].lower()


@pytest.mark.asyncio
async def test_market_order_price_zero():
    captured = []
    acct = _account_capturing(captured)
    spec = OrderSpec(transaction_type=TransactionType.BUY, quantity=1,
                     order_type=OrderType.MARKET, symbol="TCS",
                     product=ProductType.DELIVERY)
    await acct.place_order(spec)
    body = captured[0]["body"]
    assert body["pt"] == "MKT"
    assert body["pr"] == "0"
    assert body["pc"] == "CNC"             # DELIVERY -> CNC


# ── read normalization ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_portfolio_normalizes_holdings():
    acct = KotakBrokerAccount(session={"base_url": "https://e22.x"})

    async def fake_rest(method, path, *, body=None):
        return {"data": [
            {"displaySymbol": "RELIANCE", "quantity": "2", "averagePrice": "1300",
             "closingPrice": "1320", "holdingCost": "2600", "mktValue": "2640"},
            {"displaySymbol": "ZERO", "quantity": "0", "averagePrice": "100"},  # skipped
        ]}

    acct._rest = fake_rest
    p = await acct.get_portfolio()
    assert isinstance(p, Portfolio)
    assert len(p.positions) == 1
    pos = p.positions[0]
    assert pos.symbol == "RELIANCE" and pos.quantity == 2
    assert pos.pnl == 40.0                  # 2640 - 2600
    assert p.invested_value == 2600.0


@pytest.mark.asyncio
async def test_get_funds_normalizes_limits():
    acct = KotakBrokerAccount(session={})
    captured = {}

    async def fake_rest(method, path, *, body=None):
        captured["method"] = method
        captured["body"] = body
        # Flat NEST-style margin dict (real Kotak shape).
        return {"Net": "63333.14", "MarginUsed": "31425.92",
                "CollateralValue": "94759.06", "RealizedMtomPrsnt": "9507.32"}

    acct._rest = fake_rest
    funds = await acct.get_funds_and_margin()
    assert captured["method"] == "POST"            # limits is a POST
    assert captured["body"] == {"seg": "ALL", "exch": "ALL", "prod": "ALL"}
    assert funds["equity"]["available_margin"] == 63333.14
    assert funds["equity"]["used_margin"] == 31425.92
    assert funds["equity"]["collateral"] == 94759.06


@pytest.mark.asyncio
async def test_rest_wraps_post_body_in_jdata(monkeypatch):
    """Every Kotak form-POST must wrap its payload as jData={json} — the format
    the official SDK uses and a live limits call confirmed (hf-tools sent flat,
    which is broken). This guards the transport, which the method tests mock."""
    import json as _json

    import brokers.kotak.account as acct_mod

    sent = {}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, headers=None, content=None):
            sent["content"] = content

            class _R:
                def json(self_inner):
                    return {"data": {"nOrdNo": "X"}}

            return _R()

    monkeypatch.setattr(acct_mod.httpx, "AsyncClient", _FakeClient)
    acct = KotakBrokerAccount(session={"base_url": "https://e22.x", "serverId": "s"})
    await acct._rest("POST", "/quick/order/rule/ms/place", body={"ts": "RELIANCE-EQ", "tt": "BUY"})
    # Outgoing form body is exactly jData=<json of the payload>.
    assert sent["content"].startswith("jData=")
    import urllib.parse
    decoded = _json.loads(urllib.parse.parse_qs(sent["content"])["jData"][0])
    assert decoded == {"ts": "RELIANCE-EQ", "tt": "BUY"}


@pytest.mark.asyncio
async def test_get_portfolio_empty_when_no_holdings():
    from brokers.base import BrokerError

    acct = KotakBrokerAccount(session={})

    async def fake_rest(method, path, *, body=None):
        # Kotak's "no delivery holdings" error envelope.
        return {"error": [{"message": "No holdings found for this client V4YM3"}]}

    acct._rest = fake_rest
    p = await acct.get_portfolio()           # must degrade to empty, not raise
    assert p.total_value == 0.0
    assert p.positions == []


# ── auth ────────────────────────────────────────────────────────────────────
def test_session_freshness():
    import datetime

    assert _session_is_fresh(None) is False
    assert _session_is_fresh({"edit_token": "x"}) is False  # no timestamp
    today = datetime.datetime.now().isoformat()
    assert _session_is_fresh({"edit_token": "x", "logged_in_at": today}) is True
    old = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
    assert _session_is_fresh({"edit_token": "x", "logged_in_at": old}) is False


@pytest.mark.asyncio
async def test_login_descriptor_is_api_key_not_oauth():
    desc = await KotakAuth().login_descriptor(1)
    assert desc.flow == "api_key"
    assert desc.auth_url is None
    keys = {f.key for f in desc.credential_fields}
    assert {"consumer_key", "mobile_number", "ucc", "mpin", "totp_key"} <= keys


class _FakeStore(KotakStore):
    def __init__(self):
        self.saved = None

    async def get_credentials(self, user_id):
        return {
            "consumer_key": "CK", "mobile_number": "9999999999", "ucc": "UCC1",
            "mpin": "1234", "totp_key": "JBSWY3DPEHPK3PXP",  # valid base32
            "neo_fin_key": "neotradeapi",
        }

    async def load_session(self, user_id):
        return None  # force a login

    async def save_session(self, user_id, session):
        self.saved = session


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class _FakeAsyncClient:
    """Returns the login token then the validate token in call order."""

    _responses = [
        {"data": {"token": "LOGIN_TOK", "sid": "LOGIN_SID", "rid": "R1", "dataCenter": "e22"}},
        {"data": {"token": "EDIT_TOK", "sid": "EDIT_SID", "rid": "R2", "hsServerId": "SRV9"}},
    ]

    def __init__(self, *a, **k):
        self._i = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        resp = _FakeResp(self._responses[self._i])
        self._i += 1
        return resp


@pytest.mark.asyncio
async def test_login_flow_assembles_session(monkeypatch):
    import brokers.kotak.auth as auth_mod

    monkeypatch.setattr(auth_mod.httpx, "AsyncClient", _FakeAsyncClient)
    auth = KotakAuth(store=_FakeStore())
    session = await auth.get_session(1)
    assert session["edit_token"] == "EDIT_TOK"       # from validate step
    assert session["edit_sid"] == "EDIT_SID"
    assert session["serverId"] == "SRV9"
    assert session["base_url"] == "https://e22.kotaksecurities.com"
    # access-token shim returns edit_token
    assert await auth.get_access_token(1) == "EDIT_TOK"
