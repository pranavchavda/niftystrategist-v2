"""Phase C backbone — users.broker discriminator, the broker_accounts credential
store, the DB-backed Kotak store, current_broker read-routing, and
connected_brokers enumeration.

DB-touching tests run against an in-memory SQLite (the ORM uses generic
JSON/String types) so they're self-contained — no Supabase/WARP needed. Only the
``users`` + ``broker_accounts`` tables are created (other models use pgvector).
"""

import importlib.util
import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Fernet key for encrypt/decrypt_token lives in backend/.env.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from brokers.credentials import GenericCredentialStore
from brokers.kotak.auth import DBKotakStore
from brokers.registry import connected_brokers
from database.models import Base, User, UserBrokerAccount


# ── in-memory DB wiring ──────────────────────────────────────────────────────
async def _make_db(monkeypatch, *, seed_users=()):
    """Spin up an isolated SQLite DB and point get_db_session at it.

    The store + registry do ``from database.session import get_db_session``
    inside their methods, so patching the module attribute is sufficient.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c, tables=[User.__table__, UserBrokerAccount.__table__]
            )
        )
    Session = async_sessionmaker(engine, expire_on_commit=False)

    import database.session as dbsess
    monkeypatch.setattr(dbsess, "get_db_session", lambda: Session())

    if seed_users:
        async with Session() as s:
            for u in seed_users:
                s.add(User(**u))
            await s.commit()
    return engine, Session


def _load_cli_base():
    """cli-tools/ isn't a package (hyphen) — load base.py by path."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "cli-tools", "base.py")
    spec = importlib.util.spec_from_file_location("clibase", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── GenericCredentialStore ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_credentials_round_trip_and_encrypted_at_rest(monkeypatch):
    engine, Session = await _make_db(
        monkeypatch, seed_users=[{"id": 42, "email": "a@x.com", "broker": "kotak"}]
    )
    try:
        store = GenericCredentialStore("kotak")
        await store.set_credentials(42, {"consumer_key": "CK", "mpin": "7043"})
        assert await store.get_credentials(42) == {"consumer_key": "CK", "mpin": "7043"}

        # Raw column must NOT contain the plaintext secret.
        async with Session() as s:
            row = (
                await s.execute(
                    select(UserBrokerAccount).where(UserBrokerAccount.user_id == 42)
                )
            ).scalar_one()
            assert "CK" not in str(row.credentials)
            assert "7043" not in str(row.credentials)

        # Partial update keeps the untouched field.
        await store.set_credentials(42, {"mpin": "9999"})
        got = await store.get_credentials(42)
        assert got == {"consumer_key": "CK", "mpin": "9999"}

        await store.clear(42)
        assert await store.get_credentials(42) == {}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_blob_round_trip_encrypted(monkeypatch):
    engine, Session = await _make_db(
        monkeypatch, seed_users=[{"id": 7, "email": "b@x.com", "broker": "kotak"}]
    )
    try:
        store = GenericCredentialStore("kotak")
        blob = {"edit_token": "TOK", "edit_sid": "SID", "serverId": "SRV",
                "base_url": "https://e22.kotaksecurities.com"}
        await store.set_session(7, blob, broker_user_id="V4YM3")
        assert await store.get_session(7) == blob

        async with Session() as s:
            row = (
                await s.execute(
                    select(UserBrokerAccount).where(UserBrokerAccount.user_id == 7)
                )
            ).scalar_one()
            assert "_enc" in (row.session or {})          # stored encrypted
            assert "TOK" not in str(row.session)
            assert row.broker_user_id == "V4YM3"
            assert row.status == "connected"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_empty_when_no_row(monkeypatch):
    engine, _ = await _make_db(monkeypatch)
    try:
        store = GenericCredentialStore("kotak")
        assert await store.get_credentials(999) == {}
        assert await store.get_session(999) is None
    finally:
        await engine.dispose()


# ── DBKotakStore maps onto the generic store ─────────────────────────────────
@pytest.mark.asyncio
async def test_db_kotak_store_maps_creds_and_session(monkeypatch):
    engine, _ = await _make_db(
        monkeypatch, seed_users=[{"id": 3, "email": "c@x.com", "broker": "kotak"}]
    )
    try:
        # Seed creds via the generic store, then read them through DBKotakStore.
        await GenericCredentialStore("kotak").set_credentials(
            3, {"consumer_key": "CK", "mobile_number": "9999999999", "ucc": "V4YM3",
                "mpin": "7043", "totp_key": "JBSWY3DPEHPK3PXP"}
        )
        kstore = DBKotakStore()
        creds = await kstore.get_credentials(3)
        assert creds["consumer_key"] == "CK" and creds["ucc"] == "V4YM3"

        # save_session persists ucc as broker_user_id and round-trips.
        sess = {"edit_token": "T", "ucc": "V4YM3", "logged_in_at": "2026-06-02T10:00:00"}
        await kstore.save_session(3, sess)
        assert await kstore.load_session(3) == sess
    finally:
        await engine.dispose()


# ── connected_brokers enumeration ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_connected_brokers_active_first_and_deduped(monkeypatch):
    engine, Session = await _make_db(
        monkeypatch,
        seed_users=[{"id": 10, "email": "d@x.com", "broker": "kotak",
                     "upstox_access_token": "tok"}],
    )
    try:
        # Active = kotak; also has an Upstox token → both connected.
        await GenericCredentialStore("kotak").set_credentials(10, {"consumer_key": "CK"})
        brokers = await connected_brokers(10)
        assert brokers[0] == "kotak"          # active first
        assert set(brokers) == {"kotak", "upstox"}
        assert len(brokers) == len(set(brokers))   # deduped
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_connected_brokers_defaults_to_active_only(monkeypatch):
    engine, _ = await _make_db(
        monkeypatch, seed_users=[{"id": 11, "email": "e@x.com", "broker": "upstox"}]
    )
    try:
        # No tokens, no broker_accounts row → just the active broker.
        assert await connected_brokers(11) == ["upstox"]
    finally:
        await engine.dispose()


# ── current_broker / _requesting_user_id (pure logic, no DB) ─────────────────
def test_requesting_user_id_branches(monkeypatch):
    base = _load_cli_base()
    monkeypatch.setenv("NF_USER_ID", "5")
    monkeypatch.delenv("NF_AGENT_SUBPROCESS", raising=False)
    assert base._requesting_user_id() == 5

    # Agent subprocess without a user id → None (cross-account contamination guard).
    monkeypatch.delenv("NF_USER_ID", raising=False)
    monkeypatch.setenv("NF_AGENT_SUBPROCESS", "1")
    assert base._requesting_user_id() is None

    # Direct terminal use → owner.
    monkeypatch.delenv("NF_AGENT_SUBPROCESS", raising=False)
    assert base._requesting_user_id() == base.OWNER_USER_ID


def test_current_broker_reads_resolver_and_defaults(monkeypatch):
    base = _load_cli_base()
    monkeypatch.setattr(base, "_resolve_broker_sync", lambda uid: "kotak")
    assert base.current_broker(10) == "kotak"

    monkeypatch.setattr(base, "_resolve_broker_sync", lambda uid: None)
    assert base.current_broker(10) == "upstox"      # safe default on miss

    # Unresolvable user (agent subprocess, no NF_USER_ID) → default, no DB touch.
    monkeypatch.delenv("NF_USER_ID", raising=False)
    monkeypatch.setenv("NF_AGENT_SUBPROCESS", "1")
    called = {"n": 0}
    monkeypatch.setattr(base, "_resolve_broker_sync",
                        lambda uid: called.__setitem__("n", called["n"] + 1) or "kotak")
    assert base.current_broker() == "upstox"
    assert called["n"] == 0                          # never hit the DB
