#!/usr/bin/env python3
"""
Memory Cleanup Script — deduplication, fading, and low-value removal.

Analyzes existing memories and:
1. Identifies semantic duplicates (similarity > 0.85)
2. Finds consolidation candidates (similarity 0.70-0.85)
3. Detects low-value memories based on patterns
4. Applies memory fading rules (age + access count)
5. Generates report, backs up, then executes with confirmation

Usage:
    python memory_cleanup.py --analyze              # Analysis only (no changes)
    python memory_cleanup.py --execute              # Execute cleanup
    python memory_cleanup.py --backup-only          # Backup only
    python memory_cleanup.py --user user@email      # Specific user

Recommended: run weekly via cron after the daily extraction.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.models import Memory
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import numpy as np

# Configuration
DUPLICATE_THRESHOLD = 0.85      # Cosine similarity for exact duplicates
CONSOLIDATE_THRESHOLD = 0.70    # Cosine similarity for consolidation
FADE_DELETE_MONTHS = 6          # Delete if no access in X months
FADE_REDUCE_MONTHS = 3          # Reduce confidence if <3 accesses in X months
FADE_MIN_ACCESS_KEEP = 20       # Keep if accessed this many times regardless

# Low-value patterns specific to NiftyStrategist
LOW_VALUE_PATTERNS = {
    "generic_system": [
        r"system (has|includes|contains|supports)",
        r"backend (has|includes|contains)",
        r"cli.tools directory",
        r"tool (exists|available|script)",
        r"python environment is operational",
        r"niftystrategist (is|has|includes)",
    ],
    "transient_tasks": [
        r"documentation updates (are |were )?made",
        r"new tool created:",
        r"script (exists|created) for",
        r"implementing .* feature",
        r"ongoing collaboration",
    ],
    "stale_market_data": [
        r"(current|today'?s) (price|ltp|nifty|banknifty) (is|was|at) \d",
        r"market (is|was) (open|closed|trading)",
        r"position in .* (is|was) .* shares",
    ],
}


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    arr1, arr2 = np.array(vec1), np.array(vec2)
    norm1, norm2 = np.linalg.norm(arr1), np.linalg.norm(arr2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(arr1, arr2) / (norm1 * norm2))


def matches_low_value_pattern(fact: str) -> Tuple[bool, str]:
    fact_lower = fact.lower()
    for category, patterns in LOW_VALUE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, fact_lower):
                return True, category
    return False, ""


def should_fade(memory: Memory) -> Tuple[str, str]:
    """Determine if memory should be faded based on age and access patterns."""
    age_days = (datetime.now(timezone.utc) - memory.created_at.replace(tzinfo=timezone.utc)).days
    age_months = age_days / 30

    if memory.access_count >= FADE_MIN_ACCESS_KEEP:
        return "keep", f"High access count ({memory.access_count})"

    if age_months >= FADE_DELETE_MONTHS and memory.access_count == 0:
        return "delete", f"No access in {age_months:.0f} months"

    if age_months >= FADE_REDUCE_MONTHS and memory.access_count < 3:
        return "reduce_confidence", f"Only {memory.access_count} accesses in {age_months:.0f} months"

    return "keep", "Recent or accessed"


class MemoryCleanupAnalyzer:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.memories: List[Memory] = []
        self.actions: Dict[str, List[Dict]] = {
            "delete_duplicates": [],
            "consolidate": [],
            "delete_low_value": [],
            "delete_faded": [],
            "reduce_confidence": [],
            "keep": [],
        }

    async def load_memories(self, user_id: str = None):
        query = select(Memory)
        if user_id:
            query = query.where(Memory.user_id == user_id)
        result = await self.session.execute(query)
        self.memories = list(result.scalars().all())
        print(f"Loaded {len(self.memories)} memories")

    async def analyze(self):
        print("\n" + "=" * 80)
        print("MEMORY CLEANUP ANALYSIS")
        print("=" * 80 + "\n")

        await self._find_duplicates()
        await self._find_consolidation_candidates()
        await self._find_low_value()
        await self._apply_fading_rules()
        self._generate_report()

    async def _find_duplicates(self):
        print("Finding duplicates (similarity > 0.85)...")
        processed: Set[int] = set()

        for i, mem1 in enumerate(self.memories):
            if mem1.id in processed or not mem1.embedding:
                continue
            duplicates = []
            for j, mem2 in enumerate(self.memories[i + 1 :], start=i + 1):
                if mem2.id in processed or not mem2.embedding:
                    continue
                sim = cosine_similarity(mem1.embedding, mem2.embedding)
                if sim >= DUPLICATE_THRESHOLD:
                    duplicates.append({"memory": mem2, "similarity": sim})
                    processed.add(mem2.id)

            if duplicates:
                all_mems = [{"memory": mem1, "similarity": 1.0}] + duplicates
                all_mems.sort(
                    key=lambda x: (x["memory"].access_count, x["memory"].confidence, -x["memory"].id),
                    reverse=True,
                )
                keeper = all_mems[0]["memory"]
                for dup in all_mems[1:]:
                    self.actions["delete_duplicates"].append({
                        "id": dup["memory"].id,
                        "fact": dup["memory"].fact,
                        "similarity": dup["similarity"],
                        "keeper_id": keeper.id,
                        "reason": f"Duplicate of #{keeper.id} (sim: {dup['similarity']:.3f})",
                    })
        print(f"  Found {len(self.actions['delete_duplicates'])} duplicates\n")

    async def _find_consolidation_candidates(self):
        print("Finding consolidation candidates (similarity 0.70-0.85)...")
        processed: Set[int] = set()
        skip_ids = {m["id"] for m in self.actions["delete_duplicates"]}

        for i, mem1 in enumerate(self.memories):
            if mem1.id in processed or mem1.id in skip_ids or not mem1.embedding:
                continue
            for j, mem2 in enumerate(self.memories[i + 1 :], start=i + 1):
                if mem2.id in processed or mem2.id in skip_ids or not mem2.embedding:
                    continue
                sim = cosine_similarity(mem1.embedding, mem2.embedding)
                if CONSOLIDATE_THRESHOLD <= sim < DUPLICATE_THRESHOLD:
                    self.actions["consolidate"].append({
                        "id1": mem1.id, "fact1": mem1.fact,
                        "id2": mem2.id, "fact2": mem2.fact,
                        "similarity": sim,
                    })
        print(f"  Found {len(self.actions['consolidate'])} consolidation candidates\n")

    async def _find_low_value(self):
        print("Finding low-value memories...")
        skip_ids = {m["id"] for m in self.actions["delete_duplicates"]}
        for mem in self.memories:
            if mem.id in skip_ids:
                continue
            is_low_value, category = matches_low_value_pattern(mem.fact)
            if is_low_value:
                self.actions["delete_low_value"].append({
                    "id": mem.id, "fact": mem.fact,
                    "category": category, "reason": f"Low-value pattern: {category}",
                })
        print(f"  Found {len(self.actions['delete_low_value'])} low-value memories\n")

    async def _apply_fading_rules(self):
        print("Applying memory fading rules...")
        skip_ids = {m["id"] for m in self.actions["delete_duplicates"]}
        skip_ids.update({m["id"] for m in self.actions["delete_low_value"]})

        for mem in self.memories:
            if mem.id in skip_ids:
                continue
            action, reason = should_fade(mem)
            if action == "delete":
                self.actions["delete_faded"].append({
                    "id": mem.id, "fact": mem.fact,
                    "access_count": mem.access_count, "reason": reason,
                })
            elif action == "reduce_confidence":
                self.actions["reduce_confidence"].append({
                    "id": mem.id, "fact": mem.fact,
                    "current_confidence": mem.confidence,
                    "new_confidence": mem.confidence * 0.5,
                    "reason": reason,
                })
            else:
                self.actions["keep"].append({"id": mem.id, "reason": reason})

        print(f"  {len(self.actions['delete_faded'])} to delete (faded)")
        print(f"  {len(self.actions['reduce_confidence'])} to reduce confidence")
        print(f"  {len(self.actions['keep'])} to keep\n")

    def _generate_report(self):
        total = len(self.memories)
        deletions = (
            len(self.actions["delete_duplicates"])
            + len(self.actions["delete_low_value"])
            + len(self.actions["delete_faded"])
        )
        print("\n" + "=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)
        print(f"\nTotal memories:          {total}")
        print(f"Delete (duplicates):     {len(self.actions['delete_duplicates'])}")
        print(f"Delete (low-value):      {len(self.actions['delete_low_value'])}")
        print(f"Delete (faded):          {len(self.actions['delete_faded'])}")
        print(f"Total deletions:         {deletions}")
        print(f"Confidence reductions:   {len(self.actions['reduce_confidence'])}")
        print(f"Consolidation candidates:{len(self.actions['consolidate'])}")
        print(f"Remaining:               {total - deletions}")
        if total > 0:
            print(f"Reduction:               {(deletions / total) * 100:.1f}%\n")

        for key, label in [
            ("delete_duplicates", "DUPLICATES TO DELETE"),
            ("delete_low_value", "LOW-VALUE TO DELETE"),
            ("delete_faded", "FADED TO DELETE"),
        ]:
            items = self.actions[key]
            if items:
                print(f"\n{label}:")
                for item in items[:10]:
                    print(f"  #{item['id']}: {item['fact'][:80]}...")
                    print(f"    Reason: {item['reason']}")
                if len(items) > 10:
                    print(f"  ... and {len(items) - 10} more")

        if self.actions["consolidate"]:
            print(f"\nCONSOLIDATION CANDIDATES (informational):")
            for item in self.actions["consolidate"][:5]:
                print(f"  #{item['id1']} <-> #{item['id2']} (sim: {item['similarity']:.3f})")
                print(f"    {item['fact1'][:60]}...")
                print(f"    {item['fact2'][:60]}...")

    async def create_backup(self, backup_path: str):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_memories": len(self.memories),
            "memories": [
                {
                    "id": m.id, "user_id": m.user_id, "fact": m.fact,
                    "category": m.category, "confidence": m.confidence,
                    "created_at": m.created_at.isoformat(),
                    "last_accessed": m.last_accessed.isoformat() if m.last_accessed else None,
                    "access_count": m.access_count,
                }
                for m in self.memories
            ],
        }
        with open(backup_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Backup created: {backup_path}")

    async def execute_cleanup(self):
        print("\n" + "=" * 80)
        print("EXECUTING CLEANUP")
        print("=" * 80 + "\n")

        for key, label in [
            ("delete_duplicates", "duplicate"),
            ("delete_low_value", "low-value"),
            ("delete_faded", "faded"),
        ]:
            ids = [m["id"] for m in self.actions[key]]
            if ids:
                await self.session.execute(delete(Memory).where(Memory.id.in_(ids)))
                print(f"  Deleted {len(ids)} {label} memories")

        for item in self.actions["reduce_confidence"]:
            await self.session.execute(
                update(Memory).where(Memory.id == item["id"]).values(confidence=item["new_confidence"])
            )
        if self.actions["reduce_confidence"]:
            print(f"  Reduced confidence for {len(self.actions['reduce_confidence'])} memories")

        await self.session.commit()
        print("\nCleanup completed!")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Memory Cleanup Tool")
    parser.add_argument("--analyze", action="store_true", help="Analyze only (no changes)")
    parser.add_argument("--execute", action="store_true", help="Execute cleanup")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation (for cron)")
    parser.add_argument("--backup-only", action="store_true", help="Backup only")
    parser.add_argument("--user", type=str, help="Filter by user email")
    args = parser.parse_args()

    if not any([args.analyze, args.execute, args.backup_only]):
        args.analyze = True  # Default to analyze

    from dotenv import load_dotenv
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found")
        sys.exit(1)

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "?sslmode=" in database_url:
            database_url = database_url.split("?sslmode=")[0]

    connect_args = {}
    if "supabase.co" in database_url:
        connect_args = {"ssl": "require"}

    engine = create_async_engine(database_url, echo=False, connect_args=connect_args)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        analyzer = MemoryCleanupAnalyzer(session)
        await analyzer.load_memories(user_id=args.user)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = f"/tmp/niftystrategist_memory_backup_{timestamp}.json"
        await analyzer.create_backup(backup_path)

        if args.backup_only:
            return

        await analyzer.analyze()

        if args.execute:
            total_deletions = (
                len(analyzer.actions["delete_duplicates"])
                + len(analyzer.actions["delete_low_value"])
                + len(analyzer.actions["delete_faded"])
            )
            if total_deletions == 0 and not analyzer.actions["reduce_confidence"]:
                print("\nNothing to clean up!")
                return

            if not args.yes:
                confirm = input(f"\nProceed with cleanup? ({total_deletions} deletions) [y/N]: ")
                if confirm.lower() != "y":
                    print("Cancelled.")
                    return

            await analyzer.execute_cleanup()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
