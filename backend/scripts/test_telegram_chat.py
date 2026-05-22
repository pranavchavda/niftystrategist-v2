"""Local integration smoke test for Phase 2a inbound Telegram chat.

Exercises services.telegram_chat.run_telegram_turn end-to-end (daily-thread
create, history replay, orchestrator agent.run, turn persistence) WITHOUT going
through Telegram polling — so it doesn't conflict with the prod backend that
polls the same bot tokens.

Drives the dev user (999): temporarily pairs it to a fake chat_id, sends one
benign read-only message, prints the reply, then restores the prior pairing.

Run from backend/:  python scripts/test_telegram_chat.py
"""

import asyncio
import sys

from sqlalchemy import select

from database.session import get_db_session
from database.models import User as DBUser

DEV_USER_ID = 999
FAKE_CHAT_ID = -424242  # arbitrary; just has to match what we set
PROMPT = "What's the NSE market status right now? One line."


async def main() -> int:
    # Snapshot + set a known pairing for the dev user.
    async with get_db_session() as session:
        user = (
            await session.execute(select(DBUser).where(DBUser.id == DEV_USER_ID))
        ).scalar_one_or_none()
        if user is None:
            print(f"FAIL: dev user {DEV_USER_ID} not found")
            return 1
        prior_chat_id = user.telegram_chat_id
        user.telegram_chat_id = FAKE_CHAT_ID
        await session.commit()
        print(f"paired dev user {DEV_USER_ID} -> chat {FAKE_CHAT_ID} (was {prior_chat_id})")

    try:
        # 1. Auth gate: wrong chat_id must return "" (silent).
        from services.telegram_chat import run_telegram_turn

        wrong = await run_telegram_turn(DEV_USER_ID, 999999, "should be ignored")
        assert wrong == "", f"auth gate failed: expected '' for wrong chat, got {wrong!r}"
        print("PASS: unauthorized chat_id returns silent ''")

        # 2. Happy path: paired chat runs a turn and gets a reply.
        print(f"running turn: {PROMPT!r} ...")
        reply = await run_telegram_turn(DEV_USER_ID, FAKE_CHAT_ID, PROMPT)
        print("--- reply ---")
        print(reply)
        print("--- end ---")
        assert reply and reply != "(no response)", "empty reply"
        assert not reply.startswith("⚠️"), f"error reply: {reply!r}"
        print("PASS: paired chat got a non-empty reply")

        # 3. The turn was persisted to today's daily thread.
        from database.models import Message, Conversation
        async with get_db_session() as session:
            convo = (
                await session.execute(
                    select(Conversation)
                    .where(Conversation.user_id == user.email)
                    .where(Conversation.is_daily_thread.is_(True))
                    .order_by(Conversation.updated_at.desc())
                )
            ).scalars().first()
            assert convo is not None, "no daily thread created"
            msgs = (
                await session.execute(
                    select(Message)
                    .where(Message.conversation_id == convo.id)
                    .where(Message.message_id.like("tg_%"))
                )
            ).scalars().all()
            tg_user = [m for m in msgs if m.role == "user"]
            tg_asst = [m for m in msgs if m.role == "assistant"]
            assert tg_user and tg_asst, f"turn not persisted: {len(tg_user)} user / {len(tg_asst)} asst"
            print(
                f"PASS: persisted to daily thread {convo.id} "
                f"({len(tg_user)} user + {len(tg_asst)} assistant tg_* msgs)"
            )

        print("\nALL CHECKS PASSED")
        return 0
    finally:
        # Restore prior pairing.
        async with get_db_session() as session:
            user2 = (
                await session.execute(select(DBUser).where(DBUser.id == DEV_USER_ID))
            ).scalar_one_or_none()
            if user2 is not None:
                user2.telegram_chat_id = prior_chat_id
                await session.commit()
                print(f"restored dev user {DEV_USER_ID} chat_id -> {prior_chat_id}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
