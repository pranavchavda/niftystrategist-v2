#!/usr/bin/env python3
"""Memory fading job — recompute importance scores and auto-archive stale memories.

Ported from EspressoBot's `jobs/memory_distillation.py` (Part 0 only — the
importance-scoring + auto-archive piece). EB's Parts A (LLM consolidation) and B
(user-profile synthesis) are intentionally NOT ported: consolidation needs the
pgvector `embedding_halfvec` clustering NS doesn't run for memories, and profiles
need a `user_profiles` table + prompt-injection wiring NS doesn't have. Those are
separate follow-ups.

What this does, per user, daily:
  1. Recompute `importance_score` (0-1) from recency (`last_used_at`, falling back
     to `created_at`), real-use frequency (`used_count`), confidence, and category.
  2. Soft-archive (set `category='_archived'` — reversible, not deleted) memories
     scoring below ARCHIVE_IMPORTANCE_THRESHOLD that are older than
     ARCHIVE_MIN_AGE_DAYS. Retrieval (operations.py) excludes archived + ranks by
     `similarity * importance_score`, so faded memories sink then disappear.

Recency deliberately uses CONFIRMED use (`last_used_at`), not raw retrieval
(`last_accessed`): semantic-search pulls shouldn't keep junk alive. Brand-new
memories fall back to `created_at` so they don't fade before they're used.

Usage:
    python jobs/memory_fade.py            # score + archive
    python jobs/memory_fade.py --dry-run  # score, report would-archive, no writes
    python jobs/memory_fade.py --user me@x.com
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Importance score weights (sum to 1.0)
WEIGHT_RECENCY = 0.30
WEIGHT_USE = 0.25
WEIGHT_CONFIDENCE = 0.20
WEIGHT_CATEGORY = 0.15
WEIGHT_EXPLICIT = 0.10

# Category importance multipliers. NS categories (CLAUDE.md): risk_tolerance,
# position_sizing, sector_preference, trading_style, avoid_list, past_learnings,
# communication, experience_level, schedule. Durable preferences weighted high;
# schedule/task-like ones lower (they go stale faster). Unknown → 0.7.
CATEGORY_WEIGHTS = {
    "risk_tolerance": 1.0,
    "position_sizing": 1.0,
    "avoid_list": 1.0,
    "experience_level": 0.9,
    "communication": 0.9,
    "sector_preference": 0.85,
    "trading_style": 0.85,
    "past_learnings": 0.85,
    "schedule": 0.6,
}
DEFAULT_CATEGORY_WEIGHT = 0.7

# Fading thresholds (mirrors EB's calibration). An unused memory floors near
# ~0.39 once recency decays, so 0.40 is the line that actually fades. Age gate
# gives durable-but-silent preferences 6 months to accumulate real-use signal
# before anything can be auto-archived.
ARCHIVE_IMPORTANCE_THRESHOLD = 0.40
ARCHIVE_MIN_AGE_DAYS = 180


def compute_importance(
    days_since_use: float,
    confidence: float,
    category: str,
    used_count: int = 0,
) -> float:
    """Multi-factor importance (0.0-1.0). See module docstring for the recency rationale."""
    # Recency: sigmoid decay, half-life ~30 days.
    recency = 1.0 / (1.0 + math.exp((days_since_use - 30) / 10))
    # Use frequency: confirmed application only (used_count), log-scaled.
    use = min(1.0, math.log1p(used_count) / math.log1p(15))
    # Confidence (already 0-1).
    conf = min(1.0, max(0.0, confidence))
    # Category weight.
    cat_weight = CATEGORY_WEIGHTS.get(category, DEFAULT_CATEGORY_WEIGHT)
    # Explicit/consolidated bonus — NS has no consolidation, so constant 0.5.
    explicit = 0.5

    score = (
        WEIGHT_RECENCY * recency
        + WEIGHT_USE * use
        + WEIGHT_CONFIDENCE * conf
        + WEIGHT_CATEGORY * cat_weight
        + WEIGHT_EXPLICIT * explicit
    )
    return round(min(1.0, max(0.0, score)), 4)


async def _get_users(session) -> list[str]:
    result = await session.execute(
        text("SELECT DISTINCT user_id FROM memories WHERE archived = FALSE")
    )
    return [row[0] for row in result.fetchall()]


async def update_importance_scores(session, user_id: str, dry_run: bool = False) -> dict:
    """Recompute importance for a user's active memories; archive stale low-importance ones."""
    result = await session.execute(
        text("""
            SELECT id, last_used_at, used_count, confidence, category, created_at, fact
            FROM memories
            WHERE user_id = :uid AND archived = FALSE
        """),
        {"uid": user_id},
    )
    rows = result.fetchall()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    scored = 0
    would_archive: list[dict] = []

    for row in rows:
        mem_id, last_used_at, used_count, confidence, category, created_at, fact = row
        # Recency from confirmed use; fall back to created_at for never-used.
        ref_time = last_used_at or created_at or now
        days_since = (now - ref_time).total_seconds() / 86400.0

        score = compute_importance(
            days_since_use=days_since,
            confidence=confidence if confidence is not None else 1.0,
            category=category or "fact",
            used_count=used_count or 0,
        )

        mem_age_days = (now - (created_at or now)).total_seconds() / 86400.0
        archive = score < ARCHIVE_IMPORTANCE_THRESHOLD and mem_age_days > ARCHIVE_MIN_AGE_DAYS

        if archive:
            would_archive.append(
                {"id": mem_id, "score": score, "age_days": round(mem_age_days), "fact": fact[:80]}
            )

        if not dry_run:
            if archive:
                await session.execute(
                    text("UPDATE memories SET importance_score = :s, archived = TRUE, archived_at = NOW() WHERE id = :id"),
                    {"s": score, "id": mem_id},
                )
            else:
                await session.execute(
                    text("UPDATE memories SET importance_score = :s WHERE id = :id"),
                    {"s": score, "id": mem_id},
                )
        scored += 1

    return {"scored": scored, "would_archive": would_archive}


async def run_memory_fade(dry_run: bool = False, only_user: str | None = None) -> dict:
    """Main entry point — used by the scheduler and the CLI."""
    start = datetime.now(timezone.utc)
    stats = {"users": 0, "scored": 0, "archived": 0, "would_archive": []}

    async with AsyncSessionLocal() as session:
        users = [only_user] if only_user else await _get_users(session)
        stats["users"] = len(users)

        for uid in users:
            res = await update_importance_scores(session, uid, dry_run=dry_run)
            stats["scored"] += res["scored"]
            stats["would_archive"].extend(res["would_archive"])
            if not dry_run:
                stats["archived"] += len(res["would_archive"])
        if not dry_run:
            await session.commit()

    stats["archived"] = len(stats["would_archive"]) if dry_run else stats["archived"]
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(
        "memory_fade: %s — scored %d across %d users, %s %d (%.1fs)",
        "DRY-RUN" if dry_run else "applied",
        stats["scored"],
        stats["users"],
        "would archive" if dry_run else "archived",
        len(stats["would_archive"]),
        elapsed,
    )
    return stats


def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Recompute memory importance + fade stale memories")
    ap.add_argument("--dry-run", action="store_true", help="Score + report would-archive without writing")
    ap.add_argument("--user", help="Limit to a single user_id (email)")
    args = ap.parse_args()

    stats = asyncio.run(run_memory_fade(dry_run=args.dry_run, only_user=args.user))
    print(f"\nusers={stats['users']} scored={stats['scored']} "
          f"{'would_archive' if args.dry_run else 'archived'}={len(stats['would_archive'])}")
    if stats["would_archive"]:
        print(f"\n{'WOULD ARCHIVE' if args.dry_run else 'ARCHIVED'} ({len(stats['would_archive'])}):")
        for m in stats["would_archive"]:
            print(f"  [{m['id']}] score={m['score']} age={m['age_days']}d: {m['fact']}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
