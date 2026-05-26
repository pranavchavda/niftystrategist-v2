"""Regression tests for cli-tools/base.py:init_client() user scoping.

Guards against cross-account contamination: an agent-spawned CLI command
must never silently fall back to the owner's Upstox account when the
requesting user can't be identified or has no token.

Incident: 2026-05-26, thread_1779776921833 — Ashok (user 5) ran CLI tools
whose subprocess lacked NF_USER_ID, so init_client() defaulted to user 1
(owner) and returned the owner's live broker account.
"""
import importlib
import os
import sys

import pytest

_CLI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli-tools")
if _CLI_DIR not in sys.path:
    sys.path.insert(0, _CLI_DIR)


@pytest.fixture
def base(monkeypatch):
    """Import the cli-tools base module fresh, with env isolated per test."""
    for var in ("NF_USER_ID", "NF_AGENT_SUBPROCESS", "NF_ACCESS_TOKEN",
                "UPSTOX_ACCESS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    mod = importlib.import_module("base")
    importlib.reload(mod)
    return mod


def _make_client_recorder(monkeypatch, base):
    """Capture UpstoxClient(**kwargs) instead of constructing a real one."""
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(base, "UpstoxClient", FakeClient)
    return captured


def test_agent_without_user_id_fails_closed(base, monkeypatch):
    """Agent subprocess + no NF_USER_ID must refuse, not default to owner."""
    monkeypatch.setenv("NF_AGENT_SUBPROCESS", "1")
    monkeypatch.setattr(base, "_resolve_db_token_sync", lambda uid: "OWNER_TOKEN")
    with pytest.raises(SystemExit) as exc:
        base.init_client()
    assert exc.value.code == 1


def test_agent_with_zero_user_id_fails_closed(base, monkeypatch):
    """NF_USER_ID='0' is the orchestrator's 'unidentified' sentinel."""
    monkeypatch.setenv("NF_AGENT_SUBPROCESS", "1")
    monkeypatch.setenv("NF_USER_ID", "0")
    with pytest.raises(SystemExit) as exc:
        base.init_client()
    assert exc.value.code == 1


def test_non_owner_without_db_token_fails_closed(base, monkeypatch):
    """A real non-owner user with no DB token must NOT borrow env tokens."""
    monkeypatch.setenv("NF_AGENT_SUBPROCESS", "1")
    monkeypatch.setenv("NF_USER_ID", "5")
    monkeypatch.setenv("NF_ACCESS_TOKEN", "OWNER_ENV_TOKEN")
    monkeypatch.setattr(base, "_resolve_db_token_sync", lambda uid: None)
    with pytest.raises(SystemExit) as exc:
        base.init_client()
    assert exc.value.code == 1


def test_non_owner_uses_own_db_token(base, monkeypatch):
    """A non-owner with a DB token gets a client scoped to that token/user."""
    monkeypatch.setenv("NF_AGENT_SUBPROCESS", "1")
    monkeypatch.setenv("NF_USER_ID", "5")
    monkeypatch.setattr(base, "_resolve_db_token_sync", lambda uid: "ASHOK_TOKEN")
    captured = _make_client_recorder(monkeypatch, base)
    base.init_client()
    assert captured["access_token"] == "ASHOK_TOKEN"
    assert captured["user_id"] == 5
    assert captured["paper_trading"] is False


def test_owner_may_fall_back_to_env_token(base, monkeypatch):
    """Owner with no DB token may use the .env token (single-account)."""
    monkeypatch.setenv("NF_AGENT_SUBPROCESS", "1")
    monkeypatch.setenv("NF_USER_ID", "1")
    monkeypatch.setenv("NF_ACCESS_TOKEN", "OWNER_ENV_TOKEN")
    monkeypatch.setattr(base, "_resolve_db_token_sync", lambda uid: None)
    captured = _make_client_recorder(monkeypatch, base)
    base.init_client()
    assert captured["access_token"] == "OWNER_ENV_TOKEN"
    assert captured["user_id"] == 1


def test_terminal_use_defaults_to_owner(base, monkeypatch):
    """No agent marker (direct terminal use) defaults to the owner."""
    monkeypatch.setattr(base, "_resolve_db_token_sync", lambda uid: "OWNER_TOKEN")
    captured = _make_client_recorder(monkeypatch, base)
    base.init_client()
    assert captured["user_id"] == base.OWNER_USER_ID == 1
    assert captured["access_token"] == "OWNER_TOKEN"
