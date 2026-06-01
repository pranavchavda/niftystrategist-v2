"""KotakAuth — Kotak Neo TOTP+MPIN login behind the broker-neutral BrokerAuth.

Pure REST (no SDK). The daily login mints session tokens that every subsequent
``/quick/*`` REST call carries in ``Sid``/``Auth`` headers — the Kotak analogue
of an Upstox access token, with the same end-of-trading-day expiry.

Credentials and the minted session are read/written through a small
``KotakStore`` so storage is pluggable: env + local session file now (mirrors
hf-tools, so an existing Hermes ``~/.kotak-cli/session.json`` is reused), and
the per-user ``broker_accounts`` JSONB table in Phase C.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from brokers.base import BrokerAuth, BrokerAuthError, CredentialField, LoginDescriptor

logger = logging.getLogger(__name__)

_LOGIN_URL = "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
_VALIDATE_URL = "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate"
_DEFAULT_FIN_KEY = "neotradeapi"

_CREDENTIAL_FIELDS: tuple[CredentialField, ...] = (
    CredentialField("consumer_key", "Consumer Key", secret=True, required=True,
                    help_text="Kotak Neo API consumer key."),
    CredentialField("consumer_secret", "Consumer Secret", secret=True, required=False,
                    help_text="Kotak Neo API consumer secret."),
    CredentialField("mobile_number", "Mobile Number", secret=True, required=True,
                    help_text="Registered mobile (10 digits or +91…)."),
    CredentialField("ucc", "UCC", secret=True, required=True,
                    help_text="Client code — found under Profile in the Kotak app."),
    CredentialField("mpin", "MPIN", secret=True, required=True,
                    help_text="6-digit trading MPIN."),
    CredentialField("totp_key", "TOTP Secret", secret=True, required=True,
                    help_text="Authenticator secret for daily TOTP login."),
    CredentialField("neo_fin_key", "Neo Fin Key", secret=True, required=False,
                    help_text="Defaults to 'neotradeapi'."),
)


# ──────────────────────────────────────────────────────────────────────────
# Pluggable storage (env+file now → broker_accounts in Phase C)
# ──────────────────────────────────────────────────────────────────────────
class KotakStore(ABC):
    """Where a user's Kotak credentials + minted session live."""

    @abstractmethod
    async def get_credentials(self, user_id: int) -> dict:
        ...

    @abstractmethod
    async def load_session(self, user_id: int) -> Optional[dict]:
        ...

    @abstractmethod
    async def save_session(self, user_id: int, session: dict) -> None:
        ...


class EnvFileKotakStore(KotakStore):
    """Pre-Phase-C store: credentials from ``KOTAK_*`` env, session from a JSON
    file. Defaults to ``~/.kotak-cli/session.json`` so an existing hf-tools /
    Hermes session is picked up without re-login."""

    def __init__(self, session_path: Optional[str] = None):
        self.session_path = session_path or os.path.expanduser(
            os.environ.get("KOTAK_SESSION_FILE", "~/.kotak-cli/session.json")
        )

    async def get_credentials(self, user_id: int) -> dict:
        return {
            "consumer_key": os.environ.get("KOTAK_CONSUMER_KEY"),
            "consumer_secret": os.environ.get("KOTAK_CONSUMER_SECRET"),
            "mobile_number": os.environ.get("KOTAK_MOBILE")
            or os.environ.get("KOTAK_MOBILE_NUMBER"),
            "ucc": os.environ.get("KOTAK_UCC"),
            "mpin": os.environ.get("KOTAK_MPIN"),
            "totp_key": os.environ.get("KOTAK_TOTP_KEY"),
            "neo_fin_key": os.environ.get("KOTAK_NEO_FIN_KEY"),
        }

    async def load_session(self, user_id: int) -> Optional[dict]:
        try:
            with open(self.session_path) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    async def save_session(self, user_id: int, session: dict) -> None:
        try:
            os.makedirs(os.path.dirname(self.session_path), exist_ok=True)
            with open(self.session_path, "w") as fh:
                json.dump(session, fh, indent=2)
            os.chmod(self.session_path, 0o600)
        except OSError as e:
            logger.warning("Could not persist Kotak session: %s", e)


def _session_is_fresh(session: Optional[dict]) -> bool:
    """A session is usable if it has an edit_token minted on the current day
    (Kotak tokens expire end-of-trading-day)."""
    if not session or not session.get("edit_token"):
        return False
    stamp = session.get("logged_in_at")
    if not stamp:
        return False
    try:
        when = datetime.datetime.fromisoformat(stamp)
    except (ValueError, TypeError):
        return False
    return when.date() == datetime.datetime.now().date()


# ──────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────
class KotakAuth(BrokerAuth):
    broker = "kotak"

    def __init__(self, store: Optional[KotakStore] = None):
        self.store = store or EnvFileKotakStore()

    # -- session lifecycle ------------------------------------------------
    async def get_session(self, user_id: int, *, force_refresh: bool = False) -> dict:
        """Return a fresh Kotak session dict (edit_token/edit_sid/serverId/
        base_url), re-logging in via TOTP if the stored one is stale."""
        session = None if force_refresh else await self.store.load_session(user_id)
        if _session_is_fresh(session):
            return session

        creds = await self.store.get_credentials(user_id)
        session = await self._login(creds)
        await self.store.save_session(user_id, session)
        return session

    async def get_access_token(self, user_id: int, *, force_refresh: bool = False) -> Optional[str]:
        # Interface compliance: the "token" is edit_token. Callers that need the
        # full session (the account adapter) use get_session().
        try:
            session = await self.get_session(user_id, force_refresh=force_refresh)
        except BrokerAuthError:
            return None
        return session.get("edit_token")

    # -- login (pure REST) ------------------------------------------------
    async def _login(self, creds: dict) -> dict:
        import pyotp

        for key in ("consumer_key", "mobile_number", "ucc", "mpin", "totp_key"):
            if not creds.get(key):
                raise BrokerAuthError(f"Kotak login missing credential: {key}")

        fin_key = creds.get("neo_fin_key") or _DEFAULT_FIN_KEY
        headers = {
            "Authorization": creds["consumer_key"],
            "neo-fin-key": fin_key,
            "Content-Type": "application/json",
        }
        totp = pyotp.TOTP(creds["totp_key"]).now()
        mobile = creds["mobile_number"]

        async with httpx.AsyncClient(timeout=15) as client:
            login_data = await self._do_login(client, headers, mobile, creds["ucc"], totp,
                                               creds["totp_key"])
            # Step 2: validate with MPIN, carrying the login sid/token.
            vheaders = {
                **headers,
                "sid": login_data["sid"],
                "Auth": login_data["token"],
            }
            vresp = (await client.post(_VALIDATE_URL, json={"mpin": creds["mpin"]},
                                       headers=vheaders)).json()
            vdata = (vresp or {}).get("data")
            if not vdata or not vdata.get("token"):
                raise BrokerAuthError(f"Kotak 2FA validation failed: {_err(vresp)}")

        data_center = login_data.get("dataCenter", "e22")
        return {
            "consumer_key": creds["consumer_key"],
            "ucc": creds["ucc"],
            "mobile_number": mobile,
            "edit_token": vdata.get("token", login_data.get("token")),
            "edit_sid": vdata.get("sid", login_data.get("sid")),
            "edit_rid": vdata.get("rid", login_data.get("rid")),
            "serverId": vdata.get("hsServerId", vdata.get("serverId", "")),
            "data_center": data_center,
            "neo_fin_key": fin_key,
            "base_url": f"https://{str(data_center).lower()}.kotaksecurities.com",
            "logged_in_at": datetime.datetime.now().isoformat(),
            "token_type": "totp_validate",
        }

    async def _do_login(self, client, headers, mobile, ucc, totp, totp_key) -> dict:
        """Step 1 with Kotak's first-call-400 warm-up retry + ±91 mobile fallback."""
        import pyotp

        body = {"mobileNumber": mobile, "ucc": ucc, "totp": totp}
        resp = (await client.post(_LOGIN_URL, json=body, headers=headers)).json()

        attempts = 0
        while (resp or {}).get("error") and attempts < 2:
            attempts += 1
            body["totp"] = pyotp.TOTP(totp_key).now()
            mn = body["mobileNumber"]
            if "+91" not in mn and len(mn) == 10 and mn.isdigit():
                body["mobileNumber"] = "+91" + mn
            elif mn.startswith("+91") and len(mn) == 13:
                body["mobileNumber"] = mn[3:]
            resp = (await client.post(_LOGIN_URL, json=body, headers=headers)).json()

        data = (resp or {}).get("data")
        if not data or not data.get("token"):
            raise BrokerAuthError(f"Kotak login failed: {_err(resp)}")
        return data

    # -- descriptors ------------------------------------------------------
    def credential_fields(self) -> tuple[CredentialField, ...]:
        return _CREDENTIAL_FIELDS

    async def login_descriptor(self, user_id: int) -> LoginDescriptor:
        return LoginDescriptor(
            broker="kotak",
            flow="api_key",
            credential_fields=_CREDENTIAL_FIELDS,
            auth_url=None,
            notes=(
                "Connect Kotak Neo with your API consumer key + UCC + MPIN and an "
                "authenticator TOTP secret. Session refreshes automatically each "
                "trading day via TOTP."
            ),
        )


def _err(resp) -> str:
    if isinstance(resp, dict):
        errs = resp.get("error")
        if isinstance(errs, list) and errs:
            return errs[0].get("message", str(errs))
        if errs:
            return str(errs)
    return str(resp)[:200]
