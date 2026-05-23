"""
Memory Quality Judge

Evaluates candidate memories before storage using:
1. Pre-filter (regex) — rejects secrets, queryable IDs, and internal paths
2. Quality scoring (durability, specificity, actionability, novelty)
3. Semantic similarity check with existing memories
4. LLM judge for final decision (INSERT, UPDATE, CONSOLIDATE, REJECT)

Uses deepseek/deepseek-v4-flash for logical, systematic evaluation
(bake-off 2026-05-23: 15/15 judge accuracy; unifies the memory pipeline).
Fast reasoning model tuned for coding/logical tasks.

This prevents low-quality, duplicate, or redundant memories from being stored.
"""

import os
import json
import re as _re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pydantic import BaseModel
import numpy as np
from openai import AsyncOpenAI

# Initialize OpenRouter client for x-ai models
openrouter_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)


# Configuration
QUALITY_THRESHOLD = float(os.getenv("MEMORY_QUALITY_THRESHOLD", "7.0"))
SIMILARITY_CHECK_THRESHOLD = float(os.getenv("MEMORY_SIMILARITY_CHECK_THRESHOLD", "0.65"))
DUPLICATE_THRESHOLD = float(os.getenv("MEMORY_DUPLICATE_THRESHOLD", "0.85"))
CONSOLIDATE_THRESHOLD = float(os.getenv("MEMORY_CONSOLIDATE_THRESHOLD", "0.70"))

JUDGE_MODEL = os.getenv("MEMORY_JUDGE_MODEL", "deepseek/deepseek-v4-flash")


@dataclass
class QualityScore:
    """Memory quality score breakdown"""
    durability: float      # 1-10: Will this be useful long-term?
    specificity: float     # 1-10: Is this user-specific or generic?
    actionability: float   # 1-10: Does this change behavior?
    novelty: float        # 1-10: Is this new information?

    @property
    def weighted_score(self) -> float:
        """Calculate weighted average (matches weights in plan)"""
        return (
            self.durability * 0.3 +
            self.specificity * 0.25 +
            self.actionability * 0.3 +
            self.novelty * 0.15
        )

    def __str__(self) -> str:
        return (f"Quality Score: {self.weighted_score:.2f}/10\n"
                f"  - Durability: {self.durability}/10 (weight: 0.3)\n"
                f"  - Specificity: {self.specificity}/10 (weight: 0.25)\n"
                f"  - Actionability: {self.actionability}/10 (weight: 0.3)\n"
                f"  - Novelty: {self.novelty}/10 (weight: 0.15)")


@dataclass
class SimilarMemory:
    """Existing memory with similarity score"""
    id: int
    fact: str
    category: str
    confidence: float
    similarity: float
    access_count: int
    created_at: str


class JudgeDecision(BaseModel):
    """Judge's decision on what to do with candidate memory"""
    action: str  # "INSERT", "UPDATE", "CONSOLIDATE", "REJECT"
    memory_id: Optional[int] = None  # For UPDATE or CONSOLIDATE
    consolidated_fact: Optional[str] = None  # For CONSOLIDATE
    reasoning: str


# Pre-filter patterns that should NEVER be stored as memories.
# These reject secrets, live-queryable identifiers, and internal artifacts
# before any LLM call. NS-domain: Upstox/trading rather than Shopify.
_REJECT_PATTERNS = [
    # Upstox JWT access tokens (eyJ... .  ... . ...)
    (_re.compile(r'eyJ[\w-]+\.[\w-]+\.[\w-]+'), "Contains a JWT/access token"),
    # API keys, tokens, secrets
    (_re.compile(r'(?:sk-|sk-or-|AIzaSy|api[_\s]?key|api[_\s]?secret|access[_\s]?token|app[_\s]?secret|app[_\s]?key|jwt[_\s]?secret)[:\s=]?\s*\S{10,}', _re.IGNORECASE), "Contains API key/token/secret"),
    # Upstox instrument keys — queryable, and may rotate by expiry
    (_re.compile(r'(?:NSE|BSE|MCX)_(?:EQ|FO|INDEX|COM)\|', _re.IGNORECASE), "Contains an instrument key — queryable in real-time"),
    # Upstox order/trade IDs (long numeric runs) — transient, one-off
    (_re.compile(r'\b\d{12,18}\b'), "Contains an order/trade ID — transient"),
    # Fernet encryption keys (urlsafe base64, 43 chars + '=')
    (_re.compile(r'[A-Za-z0-9_-]{43}='), "Contains an encryption key / Fernet blob"),
    # Database URLs with credentials
    (_re.compile(r'postgresql://\S+:\S+@', _re.IGNORECASE), "Contains database credentials"),
    # Password patterns
    (_re.compile(r'(?:password|passwd|pwd|pin|totp[_\s]?secret)[:\s=]+\S{4,}', _re.IGNORECASE), "Contains a password/PIN/secret"),
    # Internal script/file paths (incl. extensionless cli-tools executables
    # like cli-tools/nf-order, and monitor/agents/services .py modules)
    (_re.compile(r'(?:cli-tools|monitor|agents|services|migrations)/[\w./-]+', _re.IGNORECASE), "Contains an internal script path"),
    # System capability descriptions
    (_re.compile(r'^(?:system|niftystrategist|nifty|strat|bot|agent)\s+(?:can|has|includes|integrates|supports|uses|enables|allows)', _re.IGNORECASE), "Describes system capability"),
]


def pre_filter_reject(candidate_fact: str) -> Optional[str]:
    """
    Fast pre-filter that rejects obviously bad memories before LLM scoring.
    Returns rejection reason string if rejected, None if passed.
    """
    for pattern, reason in _REJECT_PATTERNS:
        if pattern.search(candidate_fact):
            return reason
    return None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    arr1 = np.array(vec1)
    arr2 = np.array(vec2)

    dot_product = np.dot(arr1, arr2)
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


async def score_memory_quality(
    candidate_fact: str,
    category: str,
    user_context: str = "",
    user_id: str = "",
) -> QualityScore:
    """
    Score a candidate memory on quality criteria.

    Returns QualityScore with breakdown of 4 criteria.
    The scorer is told who the user is and what the agent can query live,
    so it can recognize "queryable state" facts that should score low durability.
    """

    scoring_prompt = f"""You are the Memory Quality Judge for NiftyStrategist, an AI trading assistant for the Indian stock market (NSE/BSE) that works for its operator.

WHO THE USER IS (always — this is fixed):
- Identity: {user_id or "the NiftyStrategist operator"}
- Role: A trader using NiftyStrategist to analyze markets and place trades via Upstox.
- The agent can query LIVE at any time via its `nf-*` CLI tools: portfolio holdings, open
  positions, available margin/funds, live quotes (LTP), historical OHLCV, option chains and
  greeks, technical indicators, market open/closed status, today's trades and P&L, monitor
  rules, scalp sessions. Anything queryable should NOT be a memory.

WHAT MAKES A GOOD MEMORY:
A good memory is something a future conversation, possibly weeks later, would benefit from having
injected into the system prompt — and which the agent CANNOT just look up. It is durable, identity-
specific, and shapes behavior.

Examples of GOOD memories:
- "User's risk tolerance is conservative — max 1% of capital per trade."
- "User prefers EMA crossover entries for equity intraday; UT Bot is still provisional."
- "User avoids trading in the pharma sector after past losses."
- "User wants trade rationale explained in plain language, not jargon."
- "User's father (Ashok) demos the platform to other traders."

Examples of BAD memories (these are what we want to reject):
- "User holds 65 lots of NIFTY 23750 CE."            → PORTFOLIO STATE, queryable
- "Available margin is ₹56,541."                     → FUNDS, queryable
- "NIFTY is trading at 23,810."                       → LIVE QUOTE, queryable
- "RSI on RELIANCE is 58."                            → INDICATOR, queryable
- "Order 260515000196715 filled at ₹156.60."          → TRANSIENT order detail
- "User placed a buy order on TATACHEM today."        → ONE-OFF session action
- "Monitor rule 3016 is enabled."                     → DB STATE, queryable
- "Quick functional test to confirm the tools work."  → TEST/DIAGNOSTIC
- "User wants to check today's option chain."         → SESSION TASK dressed as preference

CANDIDATE MEMORY:
Fact: {candidate_fact}
Category: {category}
{f"Conversation context: {user_context}" if user_context else ""}

SCORING CRITERIA (1-10):

1. DURABILITY (weight: 0.3) — Will this matter 1+ month from now?
   - 10: Permanent identity/role/risk-preference ("conservative risk tolerance", "avoids pharma")
   - 7:  Recurring trading-workflow preference ("prefers EMA cross for intraday entries")
   - 4:  Medium-term goal ("building a swing portfolio this quarter")
   - 1:  One-time task, current portfolio/market state, or session-specific identifier
   * HARD CAP: if the fact describes anything queryable via the `nf-*` tools
     (holdings, positions, funds, LTP, indicators, option chain, today's trades,
     monitor rules, scalp sessions, market status), DURABILITY ≤ 3.

2. SPECIFICITY (weight: 0.25) — Specific to THIS trader, not generic?
   - 10: Unique behavioral preference or rule ("never holds F&O overnight")
   - 7:  Trader's personal workflow ("reviews positions at 11:30 and 14:00")
   - 4:  Generic market info ("NSE closes at 15:30")
   - 1:  System capability or obvious context

3. ACTIONABILITY (weight: 0.3) — Will this CHANGE agent behavior in a future unrelated chat?
   - 10: Critical behavioral rule ("never recommend leverage above 2x")
   - 7:  Useful preference ("prefers concise analysis")
   - 4:  Minor stylistic preference
   - 1:  Pure information with no behavioral implication
   * Recall test: imagine this memory shows up in a future system prompt for a totally
     different question. Does it help, distract, or mislead? If distract/mislead → score ≤ 3.

4. NOVELTY (weight: 0.15) — Genuinely new vs already-known/inferable?
   - 10: New insight not derivable from code/DB/market data
   - 7:  Adds nuance
   - 4:  Minor variation
   - 1:  Duplicate or trivially derivable

Respond with JSON only:
{{
  "durability": <1-10>,
  "specificity": <1-10>,
  "actionability": <1-10>,
  "novelty": <1-10>,
  "reasoning": "<2-3 sentences. If you applied a HARD CAP (queryable state, identity confusion, transient ID, etc.), say so explicitly.>"
}}"""

    try:
        response = await openrouter_client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": scoring_prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return QualityScore(
            durability=float(result["durability"]),
            specificity=float(result["specificity"]),
            actionability=float(result["actionability"]),
            novelty=float(result["novelty"])
        )

    except Exception as e:
        print(f"⚠️  Error scoring memory quality: {e}")
        # Default to neutral scores if error
        return QualityScore(
            durability=5.0,
            specificity=5.0,
            actionability=5.0,
            novelty=5.0
        )


def find_similar_memories(
    candidate_embedding: List[float],
    existing_memories: List[Dict],
    threshold: float = SIMILARITY_CHECK_THRESHOLD
) -> List[SimilarMemory]:
    """
    Find existing memories similar to candidate

    Returns list of SimilarMemory objects sorted by similarity (highest first)
    """
    similar = []

    for mem in existing_memories:
        if not mem.get("embedding"):
            continue

        similarity = cosine_similarity(candidate_embedding, mem["embedding"])

        if similarity >= threshold:
            similar.append(SimilarMemory(
                id=mem["id"],
                fact=mem["fact"],
                category=mem.get("category", "unknown"),
                confidence=mem.get("confidence", 1.0),
                similarity=similarity,
                access_count=mem.get("access_count", 0),
                created_at=mem.get("created_at", "unknown")
            ))

    # Sort by similarity (highest first)
    similar.sort(key=lambda x: x.similarity, reverse=True)

    return similar


async def judge_with_context(
    candidate_fact: str,
    candidate_category: str,
    quality_score: QualityScore,
    similar_memories: List[SimilarMemory],
    user_id: str = "",
) -> JudgeDecision:
    """
    Final judge decision: INSERT, UPDATE, CONSOLIDATE, or REJECT.

    Use the score as a SIGNAL, not a gate. Apply qualitative judgment about
    whether this memory will help a future unrelated conversation.
    """

    # Build similar memories context
    similar_context = ""
    if similar_memories:
        similar_context = "\n\nEXISTING SIMILAR MEMORIES:\n"
        for i, mem in enumerate(similar_memories[:5], 1):  # Top 5
            similar_context += f"\n{i}. [ID {mem.id}] (similarity: {mem.similarity:.3f}, accessed: {mem.access_count}x)\n"
            similar_context += f"   Fact: {mem.fact}\n"
            similar_context += f"   Category: {mem.category}, Confidence: {mem.confidence}\n"

    judge_prompt = f"""You are the final Memory Quality Judge for NiftyStrategist. Decide INSERT / UPDATE / CONSOLIDATE / REJECT.

USER IDENTITY (the only person referred to as "the user" in our memory store):
{user_id or "the NiftyStrategist operator"}

CANDIDATE MEMORY:
Fact: {candidate_fact}
Category: {candidate_category}

QUALITY SUB-SCORES (signal, not gate):
{quality_score}
Weighted: {quality_score.weighted_score:.2f}/10
Threshold guideline: {QUALITY_THRESHOLD}/10
{similar_context if similar_context else "\n\nNO SIMILAR MEMORIES FOUND"}

THE QUESTION TO ASK YOURSELF (most important):
"In 30 days, an unrelated conversation pulls this memory into the system prompt via semantic search.
 Does it HELP, DISTRACT, or MISLEAD the agent?"
- HELP   → INSERT / UPDATE / CONSOLIDATE
- DISTRACT or MISLEAD → REJECT, even if the score is high.

HARD REJECT — regardless of score, reject any candidate that:
1. Describes live-queryable state — portfolio holdings, open positions, available margin/funds,
   current LTP/quote, technical indicator values, option chain/greeks, today's trades or P&L,
   monitor-rule or scalp-session state, market open/closed status. The agent queries this live
   via its `nf-*` tools.
2. Is a transient identifier — an Upstox order ID, trade ID, instrument key, or a strike the
   user happened to trade today.
3. Misattributes identity — says "User's name is X" or "User is Y" when X/Y is clearly someone
   mentioned IN the thread (a broker contact, another trader, a family member) rather than
   {user_id or "the operator"}.
4. Records a one-off trade/session action ("User placed a buy on TATACHEM today",
   "Squared off the NIFTY position at 15:10").
5. Captures a current-session task as if it were a preference
   ("User wants to check the option chain", "User's interest in finding momentum stocks").
6. Is a test/diagnostic conversation artifact ("Quick functional test to confirm tools work").
7. References our own internal data store paths ("User's note #429 contains...") — better stored
   inside the note, not as a memory.
8. Is a generic market fact obvious to any trader ("NSE closes at 15:30", "Nifty is an index").

PREFER INSERT when the candidate is:
- A durable identity/preference fact ("conservative risk tolerance", "avoids the pharma sector").
- A recurring trading-workflow rule ("prefers EMA-cross entries for intraday").
- A behavior-shaping preference ("wants plain-language explanations, not jargon").
- A validated past learning ("UT Bot sensitivity 1 catches more flips than 2 for the user").

DEDUPE / MERGE LOGIC:
- Similarity > 0.85 → UPDATE (replace if candidate is clearer/more current).
- Similarity 0.70-0.85 with new detail → CONSOLIDATE (write a merged fact).
- Similarity 0.70-0.85 redundant → REJECT.
- Similarity < 0.70 + passes the help/distract test → INSERT.

Respond with JSON only:
{{
  "action": "INSERT|UPDATE|CONSOLIDATE|REJECT",
  "memory_id": <existing memory ID if UPDATE/CONSOLIDATE, else null>,
  "consolidated_fact": "<merged fact if CONSOLIDATE, else null>",
  "reasoning": "<2-3 sentences. Name the hard-reject rule if you applied one.>"
}}"""

    try:
        response = await openrouter_client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        return JudgeDecision(
            action=result["action"].upper(),
            memory_id=result.get("memory_id"),
            consolidated_fact=result.get("consolidated_fact"),
            reasoning=result["reasoning"]
        )

    except Exception as e:
        print(f"⚠️  Error in judge decision: {e}")
        # Default to reject if error (safe fallback)
        return JudgeDecision(
            action="REJECT",
            memory_id=None,
            consolidated_fact=None,
            reasoning=f"Error in judge: {str(e)}"
        )


async def evaluate_memory(
    candidate_fact: str,
    candidate_category: str,
    candidate_embedding: List[float],
    existing_memories: List[Dict],
    user_context: str = "",
    user_id: str = "",
) -> Tuple[JudgeDecision, QualityScore]:
    """
    Complete memory evaluation pipeline

    0. Pre-filter obvious rejects (no LLM call)
    1. Score quality
    2. Find similar memories
    3. Get judge decision

    Returns: (JudgeDecision, QualityScore)
    """

    # Step 0: Pre-filter obvious rejects (no LLM call needed)
    reject_reason = pre_filter_reject(candidate_fact)
    if reject_reason:
        return (
            JudgeDecision(action="REJECT", reasoning=f"Pre-filter: {reject_reason}"),
            QualityScore(durability=0, specificity=0, actionability=0, novelty=0)
        )

    # Step 1: Score quality
    quality_score = await score_memory_quality(
        candidate_fact=candidate_fact,
        category=candidate_category,
        user_context=user_context,
        user_id=user_id,
    )

    # Step 2: Find similar memories
    similar_memories = find_similar_memories(
        candidate_embedding=candidate_embedding,
        existing_memories=existing_memories,
        threshold=SIMILARITY_CHECK_THRESHOLD
    )

    # Step 3: Get judge decision
    decision = await judge_with_context(
        candidate_fact=candidate_fact,
        candidate_category=candidate_category,
        quality_score=quality_score,
        similar_memories=similar_memories,
        user_id=user_id,
    )

    return decision, quality_score
