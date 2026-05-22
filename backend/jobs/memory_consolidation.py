#!/usr/bin/env python3
"""Memory consolidation job — merge near-duplicate memories into one.

Ported from EspressoBot's `jobs/memory_distillation.py` (Part A). Per user:
greedily cluster active memories by semantic similarity (pgvector halfvec cosine
distance), then merge each cluster of 2+ into a single comprehensive memory via
an LLM, archiving the source memories (`category='_archived'`, reversible).

The merged memory is inserted with only the `embedding` JSON column set; the
`memory_embedding_sync` DB trigger backfills `embedding_halfvec` automatically.

Runs after fading (jobs/memory_fade.py) so stale memories are archived — and
thus excluded from clustering — before merge.

LLM: deepseek/deepseek-v4-flash via OpenRouter (cheap, fast, near-frontier).

Usage:
    python jobs/memory_consolidation.py --dry-run   # show clusters, no LLM, no writes
    python jobs/memory_consolidation.py             # merge for real
    python jobs/memory_consolidation.py --user me@x.com
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI
from sqlalchemy import text

from database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Cheap/fast near-frontier model for batch merges (OpenRouter).
LLM_MODEL = "deepseek/deepseek-v4-flash"
EMBEDDING_MODEL = "text-embedding-3-large"  # matches NS memory embeddings

CLUSTER_DISTANCE_THRESHOLD = 0.3   # cosine distance < 0.3 (≈ similarity > 0.7) = same cluster
MIN_CLUSTER_SIZE = 2               # pairs are the most common duplicate pattern
MAX_CLUSTERS_PER_USER = 25         # bound LLM calls per run

_llm_client: Optional[AsyncOpenAI] = None
_openai_client: Optional[AsyncOpenAI] = None


def _llm() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    return _llm_client


def _openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


async def _get_users(session) -> list[str]:
    result = await session.execute(
        text("SELECT DISTINCT user_id FROM memories WHERE archived = FALSE")
    )
    return [row[0] for row in result.fetchall()]


async def find_clusters(session, user_id: str) -> list[list[dict]]:
    """Greedy semantic clustering across categories. Returns clusters of 2+ non-consolidated memories."""
    result = await session.execute(
        text("""
            SELECT id, fact, category, confidence
            FROM memories
            WHERE user_id = :uid
              AND archived = FALSE
              AND is_consolidated = FALSE
              AND embedding_halfvec IS NOT NULL
            ORDER BY created_at DESC
        """),
        {"uid": user_id},
    )
    pool = [{"id": r[0], "fact": r[1], "category": r[2], "confidence": r[3]} for r in result.fetchall()]
    if len(pool) < MIN_CLUSTER_SIZE:
        return []

    clusters: list[list[dict]] = []
    used_ids: set[int] = set()

    for seed in pool:
        if seed["id"] in used_ids:
            continue
        used_list = list(used_ids) if used_ids else [0]
        neighbors = await session.execute(
            text("""
                SELECT m.id, m.fact, m.category, m.confidence,
                       (m.embedding_halfvec <=> s.embedding_halfvec) AS distance
                FROM memories m, memories s
                WHERE s.id = :seed_id
                  AND m.user_id = :uid
                  AND m.archived = FALSE
                  AND m.is_consolidated = FALSE
                  AND m.id != :seed_id
                  AND m.id != ALL(:used)
                  AND m.embedding_halfvec IS NOT NULL
                  AND (m.embedding_halfvec <=> s.embedding_halfvec) < :threshold
                ORDER BY distance ASC
            """),
            {"seed_id": seed["id"], "uid": user_id, "threshold": CLUSTER_DISTANCE_THRESHOLD, "used": used_list},
        )
        cluster = [seed] + [
            {"id": r[0], "fact": r[1], "category": r[2], "confidence": r[3]} for r in neighbors.fetchall()
        ]
        if len(cluster) >= MIN_CLUSTER_SIZE:
            clusters.append(cluster)
            used_ids.update(m["id"] for m in cluster)
        else:
            used_ids.add(seed["id"])

    return clusters


import re

# Leading label/header noise some models prepend (stripped from output).
_LABEL_RE = re.compile(
    r"^\s*(\**\s*)?(consolidated\s+(fact|memory|past_learning)[^:]*:?\s*\**\s*)",
    re.IGNORECASE,
)
# Reasoning-preamble openers — if the output starts like this, the model leaked
# its chain-of-thought into the answer; reject rather than store garbage.
_REASONING_OPENERS = (
    "we need to", "we should", "let me", "let's", "okay", "ok,", "alright",
    "first,", "i'll", "i will", "i need to", "to consolidate", "sure,", "looking at",
)
_REASONING_MARKERS = ("the first memory", "the second memory", "these two memories", "consolidate these")


def _clean_fact(text: str) -> Optional[str]:
    """Strip label/header noise; reject output that leaked chain-of-thought."""
    if not text:
        return None
    out = text.strip()
    # Drop a leading "**Consolidated Fact:**" / "Consolidated Memory (...):" label.
    out = _LABEL_RE.sub("", out).strip()
    # Strip wrapping markdown bold/quotes.
    out = out.strip("*").strip().strip('"').strip()
    if not out:
        return None
    low = out.lower()
    if low.startswith(_REASONING_OPENERS) or any(m in low for m in _REASONING_MARKERS):
        return None  # leaked reasoning — skip this merge, keep the originals
    return out


async def consolidate_cluster(cluster: list[dict], category: str) -> Optional[str]:
    """Merge a cluster of related memories into one comprehensive fact via LLM."""
    facts = "\n".join(f"- {m['fact']}" for m in cluster)
    prompt = f"""Consolidate these {len(cluster)} related memories (category: {category}) into ONE comprehensive memory.

Memories:
{facts}

Rules:
- Preserve ALL specific details (IDs, names, numbers, dates, prices, symbols)
- If memories conflict, prefer the most specific/recent-sounding and note the change
- Combine into a single, information-dense fact
- Do not lose any actionable information
- Keep it concise but complete

Output ONLY the final consolidated fact as a single plain-text statement. Do NOT
include any preamble, reasoning, explanation, markdown headers, or labels like
"Consolidated Fact:". Start directly with the fact itself."""
    try:
        resp = await _llm().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
            # Disable reasoning so the model returns only the answer in content
            # (deepseek-v4-flash otherwise leaks chain-of-thought into content).
            extra_body={"reasoning": {"enabled": False}},
        )
        content = resp.choices[0].message.content or ""
        cleaned = _clean_fact(content)
        if cleaned is None and content.strip():
            logger.warning("consolidation: rejected leaked/empty output for cluster %s",
                           [m["id"] for m in cluster])
        return cleaned
    except Exception as e:
        logger.error("consolidation LLM failed: %s", e)
        return None


async def _generate_embedding(fact: str) -> Optional[list[float]]:
    try:
        resp = await _openai().embeddings.create(model=EMBEDDING_MODEL, input=fact)
        return resp.data[0].embedding
    except Exception as e:
        logger.error("embedding generation failed: %s", e)
        return None


async def run_consolidation(dry_run: bool = False, only_user: str | None = None) -> dict:
    """Cluster + merge near-duplicate memories. dry_run reports clusters without LLM calls or writes."""
    start = datetime.now(timezone.utc)
    stats = {"users": 0, "clusters_found": 0, "memories_consolidated": 0, "clusters": []}

    async with AsyncSessionLocal() as session:
        users = [only_user] if only_user else await _get_users(session)
        stats["users"] = len(users)

        for uid in users:
            clusters = await find_clusters(session, uid)
            if not clusters:
                continue

            for cluster in clusters[:MAX_CLUSTERS_PER_USER]:
                stats["clusters_found"] += 1
                source_ids = [m["id"] for m in cluster]
                dominant = Counter(m["category"] for m in cluster).most_common(1)[0][0]

                if dry_run:
                    stats["clusters"].append({
                        "user": uid, "size": len(cluster), "category": dominant,
                        "ids": source_ids, "facts": [m["fact"][:70] for m in cluster],
                    })
                    continue

                merged = await consolidate_cluster(cluster, dominant)
                if not merged:
                    continue
                embedding = await _generate_embedding(merged)
                max_conf = max((m["confidence"] or 1.0) for m in cluster)

                # Insert merged memory — trigger backfills embedding_halfvec from embedding.
                await session.execute(
                    text("""
                        INSERT INTO memories
                            (user_id, fact, category, confidence, embedding,
                             is_consolidated, consolidated_from, created_at, last_accessed,
                             access_count, used_count)
                        VALUES
                            (:uid, :fact, :cat, :conf, :embedding,
                             TRUE, :sources, NOW(), NOW(), 0, 0)
                    """),
                    {
                        "uid": uid, "fact": merged, "cat": dominant, "conf": max_conf,
                        "embedding": json.dumps(embedding) if embedding else None,
                        "sources": json.dumps(source_ids),
                    },
                )
                # Archive sources (non-lossy + reversible — category preserved).
                await session.execute(
                    text("UPDATE memories SET archived = TRUE, archived_at = NOW() WHERE id = ANY(:ids)"),
                    {"ids": source_ids},
                )
                stats["memories_consolidated"] += len(cluster)
                logger.info("  merged %d (%s): -> %s", len(cluster), dominant, merged[:70])

            if not dry_run:
                await session.commit()

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(
        "memory_consolidation: %s — %d clusters, %d memories merged across %d users (%.1fs)",
        "DRY-RUN" if dry_run else "applied",
        stats["clusters_found"], stats["memories_consolidated"], stats["users"], elapsed,
    )
    return stats


def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Consolidate near-duplicate memories")
    ap.add_argument("--dry-run", action="store_true", help="Show clusters without LLM calls or writes")
    ap.add_argument("--user", help="Limit to a single user_id (email)")
    args = ap.parse_args()

    stats = asyncio.run(run_consolidation(dry_run=args.dry_run, only_user=args.user))
    print(f"\nusers={stats['users']} clusters={stats['clusters_found']} merged={stats['memories_consolidated']}")
    if args.dry_run and stats["clusters"]:
        print(f"\nWOULD MERGE {len(stats['clusters'])} clusters:")
        for c in stats["clusters"]:
            print(f"\n  [{c['user']}] {c['size']} memories ({c['category']}) ids={c['ids']}:")
            for f in c["facts"]:
                print(f"     - {f}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
