"""One-off probe/admin: read or update a user's registered Upstox static IPs.

Upstox extended static-IP enforcement to per-user account reads (UDAPI1154),
not just orders. This reads the currently-registered primary/secondary IPs for
a user, and (with --set) updates them via PUT /v2/user/ip.

Run from backend/:
  python -m scripts.probe_static_ip get 1
  python -m scripts.probe_static_ip get 5
  python -m scripts.probe_static_ip set 5 <primary_ip> <secondary_ip>

NOTE: PUT is limited to once per CALENDAR WEEK and invalidates the user's
access token (re-auth needed afterward). Be sure the IPs are correct.
"""
import asyncio
import json
import sys

import httpx

BASE = "https://api.upstox.com/v2/user/ip"


async def _token(user_id: int) -> str | None:
    from api.upstox_oauth import get_user_upstox_token
    return await get_user_upstox_token(user_id)


def _headers(token: str) -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


async def cmd_get(user_id: int) -> int:
    token = await _token(user_id)
    if not token:
        print(f"FATAL: no token for user {user_id}")
        return 2
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(BASE, headers=_headers(token))
    print(f"user {user_id} GET {BASE} -> {r.status_code}")
    print(json.dumps(r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text, indent=2))
    return 0 if r.status_code < 400 else 1


async def cmd_set(user_id: int, primary: str, secondary: str | None) -> int:
    token = await _token(user_id)
    if not token:
        print(f"FATAL: no token for user {user_id}")
        return 2
    body: dict = {"primary_ip": primary}
    if secondary:
        body["secondary_ip"] = secondary
    print(f"user {user_id} PUT {BASE} body={body}")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.put(BASE, headers=_headers(token), json=body)
    print(f"-> {r.status_code}")
    print(json.dumps(r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text, indent=2))
    return 0 if r.status_code < 400 else 1


async def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    uid = int(sys.argv[2])
    if cmd == "get":
        return await cmd_get(uid)
    if cmd == "set":
        primary = sys.argv[3]
        secondary = sys.argv[4] if len(sys.argv) > 4 else None
        return await cmd_set(uid, primary, secondary)
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
