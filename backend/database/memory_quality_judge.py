"""
Memory Quality Judge

Evaluates candidate memories before storage using:
1. Quality scoring (durability, specificity, actionability, novelty)
2. Semantic similarity check with existing memories
3. LLM judge for final decision (INSERT, UPDATE, CONSOLIDATE, REJECT)

Uses x-ai/grok-code-fast-1 for logical, systematic evaluation.
Fast reasoning model tuned for coding/logical tasks.

This prevents low-quality, duplicate, or redundant memories from being stored.
"""

import os
import json
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
    user_context: str = ""
) -> QualityScore:
    """
    Score a candidate memory on quality criteria using Grok Code Fast.

    Uses x-ai/grok-code-fast-1 for logical, systematic evaluation.

    Returns QualityScore with breakdown of 4 criteria
    """

    scoring_prompt = f"""You are a Memory Quality Judge. Score this candidate memory on 4 criteria (1-10 scale).

CANDIDATE MEMORY:
Fact: {candidate_fact}
Category: {category}
{f"User Context: {user_context}" if user_context else ""}

SCORING CRITERIA:

1. DURABILITY (weight: 0.3)
   - Will this be useful in 1+ months, or is it a one-time task?
   - 10: Permanent business context (e.g., "sells espresso machines")
   - 7: Recurring preference (e.g., "prefers GraphQL over bash")
   - 4: Medium-term project (e.g., "working on Black Friday promo")
   - 1: One-time task (e.g., "update product X price today")

2. SPECIFICITY (weight: 0.25)
   - Is this specific to THIS user, or generic system info?
   - 10: Unique user preference/context (e.g., "contacts vendor X for Y")
   - 7: User's business specifics (e.g., "sells brands A, B, C")
   - 4: Commonly known (e.g., "store uses Shopify")
   - 1: Generic system info (e.g., "system has bash-tools directory")

3. ACTIONABILITY (weight: 0.3)
   - Does this change how the bot should behave/respond?
   - 10: Critical behavioral instruction (e.g., "always check Price to Set column")
   - 7: Strong preference (e.g., "prefers concise email drafts")
   - 4: Minor preference (e.g., "uses 'Matte' not 'Matt'")
   - 1: No behavioral impact (e.g., "product X exists")

4. NOVELTY (weight: 0.15)
   - Is this new information or redundant?
   - 10: Completely new insight
   - 7: Adds detail to existing knowledge
   - 4: Minor variation of known info
   - 1: Duplicate or already well-known

Respond with JSON only:
{{
  "durability": <1-10>,
  "specificity": <1-10>,
  "actionability": <1-10>,
  "novelty": <1-10>,
  "reasoning": "<brief explanation of scores>"
}}"""

    try:
        response = await openrouter_client.chat.completions.create(
            model="x-ai/grok-code-fast-1",
            messages=[{"role": "user", "content": scoring_prompt}],
            temperature=0.3,  # Grok supports temperature
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
    similar_memories: List[SimilarMemory]
) -> JudgeDecision:
    """
    Final judge decision: INSERT, UPDATE, CONSOLIDATE, or REJECT

    Shows similar memories to LLM and asks for decision with reasoning
    """

    # Build similar memories context
    similar_context = ""
    if similar_memories:
        similar_context = "\n\nEXISTING SIMILAR MEMORIES:\n"
        for i, mem in enumerate(similar_memories[:5], 1):  # Top 5
            similar_context += f"\n{i}. [ID {mem.id}] (similarity: {mem.similarity:.3f}, accessed: {mem.access_count}x)\n"
            similar_context += f"   Fact: {mem.fact}\n"
            similar_context += f"   Category: {mem.category}, Confidence: {mem.confidence}\n"

    judge_prompt = f"""You are a Memory Quality Judge. Decide what to do with this candidate memory.

CANDIDATE MEMORY:
Fact: {candidate_fact}
Category: {candidate_category}

QUALITY SCORE: {quality_score.weighted_score:.2f}/10
{quality_score}

THRESHOLD: {QUALITY_THRESHOLD}/10 (minimum to store)
{similar_context if similar_context else "\n\nNO SIMILAR MEMORIES FOUND"}

DECISION RULES:
1. If quality score < {QUALITY_THRESHOLD}: REJECT (unless it updates a high-value memory)
2. If similarity > 0.85 with existing memory: UPDATE (replace old with new if better)
3. If similarity 0.70-0.85 and adds new detail: CONSOLIDATE (merge both into one)
4. If similarity 0.70-0.85 but redundant: REJECT
5. If similarity < 0.70 and quality ≥ {QUALITY_THRESHOLD}: INSERT (store as new)

ACTIONS:
- INSERT: Store as new memory (high quality, novel)
- UPDATE: Replace existing memory ID with this one (duplicate but better)
- CONSOLIDATE: Merge with existing memory ID (similar but both have value)
- REJECT: Don't store (low quality or redundant)

Respond with JSON only:
{{
  "action": "INSERT|UPDATE|CONSOLIDATE|REJECT",
  "memory_id": <existing memory ID if UPDATE/CONSOLIDATE, else null>,
  "consolidated_fact": "<merged fact if CONSOLIDATE, else null>",
  "reasoning": "<explain your decision in 1-2 sentences>"
}}"""

    try:
        response = await openrouter_client.chat.completions.create(
            model="x-ai/grok-code-fast-1",
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0.3,  # Grok supports temperature
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
    user_context: str = ""
) -> Tuple[JudgeDecision, QualityScore]:
    """
    Complete memory evaluation pipeline

    1. Score quality
    2. Find similar memories
    3. Get judge decision

    Returns: (JudgeDecision, QualityScore)
    """

    # Step 1: Score quality
    quality_score = await score_memory_quality(
        candidate_fact=candidate_fact,
        category=candidate_category,
        user_context=user_context
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
        similar_memories=similar_memories
    )

    return decision, quality_score
