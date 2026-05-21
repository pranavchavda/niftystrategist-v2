"""End-to-end smoke test for the /api/telegram endpoints.

Run with the backend already up (./dev.sh) and a real bot token in env:

    cd backend
    BOT_TOKEN='123:abc' venv/bin/python scripts/test_telegram_api.py

Uses the dev-token auth path (user_id=999). The script never prints the token.
"""

import os
import sys
import time

import httpx

API = os.getenv("NF_API", "http://localhost:8000")
AUTH = {"Authorization": "Bearer dev-token-test"}


def log(msg: str) -> None:
    print(f"  → {msg}")


def header(msg: str) -> None:
    print(f"\n== {msg} ==")


def main() -> int:
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("BOT_TOKEN env var required. Get one from @BotFather.")
        return 1

    client = httpx.Client(base_url=API, headers=AUTH, timeout=15.0)

    header("1. GET /api/telegram/status (before)")
    r = client.get("/api/telegram/status")
    log(f"HTTP {r.status_code}: {r.json()}")
    assert r.status_code == 200
    initial = r.json()

    header("2. POST /api/telegram/bot-token with INVALID token")
    r = client.post("/api/telegram/bot-token", json={"token": "0:invalid"})
    log(f"HTTP {r.status_code}: {r.json()}")
    assert r.status_code == 400, "invalid token should be rejected"

    header("3. POST /api/telegram/bot-token with VALID token")
    r = client.post("/api/telegram/bot-token", json={"token": token})
    log(f"HTTP {r.status_code}: {r.json()}")
    assert r.status_code == 200, r.text
    bot_username = r.json().get("bot_username")
    assert bot_username, "expected bot_username in response"
    log(f"Bot username: @{bot_username}")

    header("4. GET /api/telegram/status (after save)")
    r = client.get("/api/telegram/status")
    log(f"HTTP {r.status_code}: {r.json()}")
    assert r.status_code == 200
    s = r.json()
    assert s["configured"] is True
    assert s["paired"] is False
    assert s["bot_username"] == bot_username

    header("5. PUT /api/telegram/notification-prefs")
    prefs = {"monitor_fire": True, "awakening": True, "system": False, "order_fill": True}
    r = client.put("/api/telegram/notification-prefs", json={"prefs": prefs})
    log(f"HTTP {r.status_code}: {r.json()}")
    assert r.status_code == 200
    assert r.json()["notification_prefs"] == prefs

    header("6. GET /api/telegram/status (after prefs)")
    r = client.get("/api/telegram/status")
    log(f"HTTP {r.status_code}: {r.json()}")
    assert r.json()["notification_prefs"] == prefs

    header("7. DELETE /api/telegram/bot-token")
    r = client.delete("/api/telegram/bot-token")
    log(f"HTTP {r.status_code}: {r.json()}")
    assert r.status_code == 200

    header("8. GET /api/telegram/status (after delete)")
    r = client.get("/api/telegram/status")
    log(f"HTTP {r.status_code}: {r.json()}")
    s = r.json()
    assert s["configured"] is False
    assert s["paired"] is False
    assert s["bot_username"] is None

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
