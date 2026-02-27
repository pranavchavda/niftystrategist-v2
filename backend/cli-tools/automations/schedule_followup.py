#!/usr/bin/env python3
"""
Schedule Follow-Up - Schedule a one-time follow-up task for a conversation thread.

Creates a workflow_definitions row with frequency='once' and a calculated scheduled_at
datetime based on a natural language delay (e.g. "2 days", "1 week", "30 minutes").
Optionally pokes the scheduler API to activate the follow-up immediately.

Usage:
    python cli-tools/automations/schedule_followup.py --thread-id "thread_abc" --user-id user@email.com --delay "2 days" --prompt "Check RELIANCE position performance"
    python cli-tools/automations/schedule_followup.py --thread-id "thread_abc" --user-id user@email.com --delay "1 week" --prompt "Review portfolio P&L" --timeout 600
"""

TOOL_META = {
    "name": "schedule_followup",
    "use_when": "User agrees to a follow-up check. Need to monitor something after a delay. Want to revisit results after changes take effect.",
    "not_for": "Recurring automations (use /automations UI instead). Immediate actions that should happen now.",
    "preferred_over": "Manual reminders or asking the user to come back later.",
    "examples": [
        'python cli-tools/automations/schedule_followup.py --thread-id "thread_abc123" --user-id user@email.com --delay "2 days" --prompt "Check RELIANCE position — did it hit target?"',
        'python cli-tools/automations/schedule_followup.py --thread-id "thread_xyz" --user-id user@email.com --delay "1 week" --prompt "Review portfolio P&L after rebalancing" --timeout 600',
    ],
}

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import asyncio
import json
import re
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Natural language delay parsing
# ---------------------------------------------------------------------------

UNIT_MAP = {
    "s": "seconds",
    "sec": "seconds",
    "secs": "seconds",
    "second": "seconds",
    "seconds": "seconds",
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
    "w": "weeks",
    "wk": "weeks",
    "wks": "weeks",
    "week": "weeks",
    "weeks": "weeks",
}


def parse_delay(delay_str: str) -> timedelta:
    """Parse a natural-language delay string into a timedelta.

    Supports formats like:
        "2 days", "48 hours", "1 week", "30 minutes", "3h", "1d", "2w"

    Falls back to dateparser if installed and simple parsing fails.
    """
    text = delay_str.strip().lower()

    # Try simple pattern: number + optional space + unit
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([a-z]+)$", text)
    if match:
        amount = float(match.group(1))
        unit_raw = match.group(2)
        unit = UNIT_MAP.get(unit_raw)
        if unit:
            return timedelta(**{unit: amount})

    # Fallback: try dateparser if available
    try:
        import dateparser

        future_dt = dateparser.parse(
            f"in {text}",
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        )
        if future_dt:
            delta = future_dt - datetime.now(timezone.utc).replace(tzinfo=None)
            if delta.total_seconds() > 0:
                return delta
    except ImportError:
        pass

    raise ValueError(
        f"Cannot parse delay '{delay_str}'. "
        "Use formats like '2 days', '48 hours', '1 week', '30 minutes'."
    )


# ---------------------------------------------------------------------------
# DB insertion
# ---------------------------------------------------------------------------


async def insert_workflow(
    *,
    thread_id: str,
    user_id: int,
    prompt: str,
    scheduled_at: datetime,
    name: str,
    agent_hint: str | None,
    timeout: int,
) -> dict:
    """Insert a follow-up row into workflow_definitions and return its id."""
    import asyncpg

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in environment")

    # asyncpg expects the postgresql:// scheme (not postgres://)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Strip query params like ?sslmode=require — we pass ssl explicitly
    if "?" in db_url:
        db_url = db_url.split("?")[0]

    ssl = "require" if "supabase.co" in db_url else None

    # Truncate name to 100 chars (DB constraint)
    name = name[:100]

    # Strip tzinfo for naive timestamp (DB uses naive timestamps)
    if scheduled_at.tzinfo is not None:
        scheduled_at = scheduled_at.replace(tzinfo=None)

    conn = await asyncpg.connect(db_url, ssl=ssl)
    try:
        # Try inserting; if name collides, append a timestamp suffix
        for attempt in range(3):
            try_name = name if attempt == 0 else f"{name[:86]} ({datetime.now(timezone.utc).strftime('%H%M%S')})"
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO workflow_definitions
                        (user_id, name, prompt, agent_hint, thread_id,
                         enabled, frequency, scheduled_at, timeout_seconds,
                         notify_on_complete, notify_on_failure, next_run_at)
                    VALUES
                        ($1, $2, $3, $4, $5,
                         true, 'once', $6, $7,
                         true, true, $8)
                    RETURNING id, name, scheduled_at
                    """,
                    user_id,
                    try_name,
                    prompt,
                    agent_hint,
                    thread_id,
                    scheduled_at,
                    timeout,
                    scheduled_at,  # next_run_at — separate param to avoid asyncpg type deduction error
                )
                return {
                    "workflow_id": row["id"],
                    "name": row["name"],
                    "scheduled_at": row["scheduled_at"].isoformat(),
                }
            except asyncpg.UniqueViolationError:
                if attempt == 2:
                    raise
                continue
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# API activation
# ---------------------------------------------------------------------------


async def activate_workflow(workflow_id: int, auth_token: str | None) -> dict | None:
    """POST to the scheduler API to register the follow-up."""
    import httpx

    base_url = os.getenv("INTERNAL_API_URL", "http://localhost:8000")
    url = f"{base_url}/api/workflows/followup/activate/{workflow_id}"
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers)
            if resp.status_code < 300:
                return resp.json()
            else:
                return {
                    "activation_error": f"HTTP {resp.status_code}: {resp.text[:200]}"
                }
    except Exception as exc:
        return {"activation_error": str(exc)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def resolve_user_id(user_id_arg: str) -> int:
    """Accept either an integer user ID or an email, returning the integer DB ID."""
    import asyncpg
    try:
        return int(user_id_arg)
    except ValueError:
        pass

    # It's an email — look up the integer ID
    db_url = os.getenv("DATABASE_URL", "")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "?" in db_url:
        db_url = db_url.split("?")[0]
    ssl = "require" if "supabase.co" in db_url else None

    conn = await asyncpg.connect(db_url, ssl=ssl)
    try:
        row = await conn.fetchrow("SELECT id FROM users WHERE email = $1", user_id_arg)
        if not row:
            print(json.dumps({"error": f"User '{user_id_arg}' not found"}))
            sys.exit(1)
        return row["id"]
    finally:
        await conn.close()


async def async_main(args: argparse.Namespace) -> None:
    # 0. Resolve user ID (accept email or integer)
    user_id = await resolve_user_id(args.user_id)

    # 1. Parse delay into absolute datetime
    try:
        delta = parse_delay(args.delay)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)

    scheduled_at = datetime.now(timezone.utc).replace(tzinfo=None) + delta

    # 2. Build a name if not provided
    name = args.name
    if not name:
        name = f"Follow up: {args.prompt[:80]}"
    name = name[:100]

    # 3. Insert into DB
    try:
        result = await insert_workflow(
            thread_id=args.thread_id,
            user_id=user_id,
            prompt=args.prompt,
            scheduled_at=scheduled_at,
            name=name,
            agent_hint=args.agent_hint,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(json.dumps({"error": f"DB insert failed: {exc}"}))
        sys.exit(1)

    # 4. Poke the scheduler API (best-effort)
    activation = await activate_workflow(result["workflow_id"], args.auth_token)

    # 5. Print structured JSON output
    output = {
        "status": "scheduled",
        "workflow_id": result["workflow_id"],
        "name": result["name"],
        "thread_id": args.thread_id,
        "scheduled_at": result["scheduled_at"],
        "delay": args.delay,
        "message": f"Follow-up scheduled for {result['scheduled_at']} (in {args.delay})",
    }
    if activation and "activation_error" in activation:
        output["activation_warning"] = activation["activation_error"]
    elif activation:
        output["activation"] = "ok"

    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Schedule a one-time follow-up task for a conversation thread"
    )
    parser.add_argument(
        "--thread-id",
        required=True,
        help="Conversation thread ID to bind this follow-up to",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="User ID (integer) or email — both accepted",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="The prompt to execute when the follow-up fires",
    )
    parser.add_argument(
        "--delay",
        required=True,
        help='Natural language delay: "2 days", "48 hours", "1 week", "30 minutes"',
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Workflow name (max 100 chars). Auto-generated from prompt if omitted.",
    )
    parser.add_argument(
        "--agent-hint",
        default=None,
        help='Optional agent hint: "web_search", "vision", etc.',
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Execution timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--auth-token",
        default=None,
        help="Optional JWT token for the scheduler activation API call",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
