"""Memory → curated user-profile synthesis (ported from EspressoBot).

Synthesizes a small, durable per-user profile from accumulated memories and
stores it in `user_profiles` (profile JSONB + <=200-word profile_text). The
profile_text is injected verbatim into the prompt by UserProfileCapability /
the legacy inline path — it is the FROZEN, always-injected memory layer
(distinct from per-query semantic recall).

Runs nightly after memory fade + consolidation (so it reads the cleaned,
de-duplicated memory set). See:
  - docs/plans/2026-05-23-prefix-cache-memory-port.md
  - services/scheduler.py::_run_memory_maintenance

NS conventions: memories filtered by `archived = FALSE` (boolean column, not
EB's `_archived` category); naive UTC timestamps.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI
from sqlalchemy import text

from database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Cheap/fast near-frontier model (OpenRouter) — same as consolidation job.
LLM_MODEL = os.getenv("MEMORY_PROFILE_MODEL", "deepseek/deepseek-v4-flash")
MAX_MEMORIES = 100        # cap memories fed to the synthesizer
MAX_PROFILE_TOKENS = 2000

_llm_client: Optional[AsyncOpenAI] = None


def _llm() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _llm_client


def _extract_json(text_in: str) -> dict:
    """Best-effort JSON extraction from a (possibly fenced) LLM response."""
    if not text_in:
        return {}
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text_in, re.DOTALL)
    candidate = fence.group(1).strip() if fence else text_in.strip()
    try:
        return json.loads(candidate)
    except Exception:
        # Fall back to the outermost {...} span
        brace = re.search(r"\{.*\}", candidate, re.DOTALL)
        if brace:
            try:
                return json.loads(brace.group(0))
            except Exception:
                return {}
        return {}


async def _get_users(session) -> list[str]:
    result = await session.execute(
        text("SELECT DISTINCT user_id FROM memories WHERE archived = FALSE")
    )
    return [row[0] for row in result.fetchall()]


async def synthesize_user_profile(session, user_id: str) -> bool:
    """Synthesize the evolving profile for one user from active memories.

    Returns True if the profile was (re)written, False if up-to-date or skipped.
    Idempotent: re-synthesizes only when the active memory count changed.
    """
    # Skip if the memory count hasn't changed since last synthesis.
    existing = (
        await session.execute(
            text("SELECT memory_count_at_synthesis FROM user_profiles WHERE user_id = :uid"),
            {"uid": user_id},
        )
    ).fetchone()

    current_count = (
        await session.execute(
            text("SELECT COUNT(*) FROM memories WHERE user_id = :uid AND archived = FALSE"),
            {"uid": user_id},
        )
    ).scalar()

    if existing and existing[0] == current_count:
        logger.info("  profile up-to-date for %s (%d memories)", user_id, current_count)
        return False

    rows = (
        await session.execute(
            text(
                """
                SELECT fact, category, confidence
                FROM memories
                WHERE user_id = :uid AND archived = FALSE
                ORDER BY COALESCE(importance_score, 1.0) DESC,
                         confidence DESC, access_count DESC, created_at DESC
                LIMIT :lim
                """
            ),
            {"uid": user_id, "lim": MAX_MEMORIES},
        )
    ).fetchall()

    memories = [{"fact": r[0], "category": r[1], "confidence": r[2]} for r in rows]
    if not memories:
        return False

    memory_list = "\n".join(f"- [{m['category']}] {m['fact']}" for m in memories)

    prompt = f"""You are synthesizing a user profile from extracted memories about a user of an AI trading assistant for the Indian stock market (NSE/BSE).

There are {len(memories)} memories:
{memory_list}

Generate TWO outputs:

1. A structured JSON profile:
{{
  "experience_level": "beginner/intermediate/advanced if known",
  "risk_tolerance": "their risk appetite if known",
  "trading_style": ["intraday/swing/F&O/equity/options preferences"],
  "position_sizing": "how they size positions / capital constraints if known",
  "sector_preferences": ["sectors or instruments they favor or avoid"],
  "avoid_list": ["things they never want to do / stocks they avoid"],
  "communication_style": "how they prefer the assistant to communicate",
  "schedule": "trading schedule / awakening preferences if known",
  "key_facts": ["other important durable facts that don't fit above"]
}}

2. A concise markdown profile summary (max 200 words) the assistant can use to personalize its trading guidance. Be factual; do not invent details not supported by the memories.

Respond with ONLY this JSON:
{{"profile": {{...the structured profile...}}, "profile_text": "...the markdown summary..."}}"""

    try:
        response = await _llm().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=MAX_PROFILE_TOKENS,
            extra_body={"reasoning": {"enabled": False}},
        )
        content = response.choices[0].message.content or ""
        if not content:
            content = getattr(response.choices[0].message, "reasoning", "") or ""
        result = _extract_json(content)
        profile = result.get("profile", {}) or {}
        profile_text = (result.get("profile_text", "") or "").strip()

        if not profile_text:
            logger.warning("  profile synthesis returned empty text for %s — skipping write", user_id)
            return False

        await session.execute(
            text(
                """
                INSERT INTO user_profiles (user_id, profile, profile_text, last_synthesized, memory_count_at_synthesis)
                VALUES (:uid, :profile, :profile_text, (NOW() AT TIME ZONE 'utc'), :count)
                ON CONFLICT (user_id) DO UPDATE SET
                    profile = :profile,
                    profile_text = :profile_text,
                    last_synthesized = (NOW() AT TIME ZONE 'utc'),
                    memory_count_at_synthesis = :count
                """
            ),
            {
                "uid": user_id,
                "profile": json.dumps(profile),
                "profile_text": profile_text,
                "count": current_count,
            },
        )
        logger.info("  profile synthesized for %s (%d chars, %d memories)", user_id, len(profile_text), current_count)
        return True

    except Exception as e:
        logger.error("profile synthesis failed for %s: %s", user_id, e)
        return False


async def run_profile_synthesis(dry_run: bool = False) -> dict:
    """Synthesize profiles for all users with active memories.

    dry_run is accepted for symmetry with the other memory jobs; synthesis has
    no destructive effect, so a dry run simply skips the DB commit.
    """
    stats = {"users": 0, "synthesized": 0}
    async with AsyncSessionLocal() as session:
        users = await _get_users(session)
        stats["users"] = len(users)
        for user_id in users:
            try:
                changed = await synthesize_user_profile(session, user_id)
                if changed:
                    stats["synthesized"] += 1
            except Exception:
                logger.exception("profile synthesis errored for %s", user_id)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return stats


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    print(asyncio.run(run_profile_synthesis(dry_run="--dry-run" in sys.argv)))
