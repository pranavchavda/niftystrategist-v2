"""Kotak Neo implementation of the broker-agnostic account layer.

Mirrors the Upstox package shape. **Pure REST + pyotp — no broker SDK.**
hf-tools proved the ``neo_api_client`` SDK returns a wrong PROD base URL, so it
(and we) authenticate and trade entirely over Kotak's REST API:
  * login  -> POST mis.kotaksecurities.com/login/1.0/tradeApiLogin (TOTP)
  * 2fa    -> POST .../tradeApiValidate (MPIN) -> session tokens
  * trade  -> {base_url}/quick/order/... and /quick/user/... , /portfolio/v1/...
Session tokens (edit_token/edit_sid/serverId/base_url) expire end-of-trading-day,
exactly like Upstox. Only deps are ``httpx`` + ``pyotp`` (both already present).

Mappings derived from github.com/pranavchavda/hf-tools (Kotak Neo CLI suite).
"""

from brokers.kotak.instruments import KotakInstrumentResolver
from brokers.kotak.account import KotakBrokerAccount
from brokers.kotak.auth import KotakAuth

__all__ = ["KotakInstrumentResolver", "KotakBrokerAccount", "KotakAuth"]
