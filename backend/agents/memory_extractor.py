"""
Memory Extraction Agent - Extracts trading memories via OpenRouter

This agent:
1. Reviews entire conversation history
2. Identifies facts, preferences, and context using LLM
3. Categorizes memories appropriately
4. Returns structured memory objects with embeddings

Uses OpenRouter for LLM access. Model configurable via MEMORY_EXTRACTION_MODEL env var.
"""

import os
import re
import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Default model for memory extraction - cheap, fast, good at JSON
# Override with MEMORY_EXTRACTION_MODEL env var
DEFAULT_MEMORY_MODEL = "x-ai/grok-4.1-fast"


class ExtractedMemory(BaseModel):
    """A single extracted memory"""
    fact: str = Field(description="The extracted fact or preference - be specific and concise")
    category: str = Field(description="Category: fact, preference, context, or task")
    confidence: float = Field(description="Confidence score 0.0-1.0 based on explicitness", ge=0.0, le=1.0)
    reasoning: str = Field(description="Brief explanation of why this memory is important")
    is_ephemeral: bool = Field(default=False, description="True if this is a one-time task or temporary information")


class MemoryExtractionResult(BaseModel):
    """Result of memory extraction"""
    memories: List[ExtractedMemory] = Field(default_factory=list, description="List of 5-15 extracted memories")
    summary: str = Field(description="Conversation title in format: [Emoji] + 3-4 words (e.g., '☕ Coffee Equipment Setup', '📧 Email System Check')")


def _extract_json_from_response(text: str) -> str:
    """Extract JSON from a response that may be wrapped in markdown fences."""
    if not text:
        return text
    # Try to extract from ```json ... ``` or ``` ... ``` fences
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    return text.strip()


class MemoryExtractor:
    """
    Agent that extracts memories from conversation history via OpenRouter.

    Uses json_object response format (broadly supported) with Pydantic parsing.
    Model is configurable via MEMORY_EXTRACTION_MODEL env var.
    """

    def __init__(self):
        """Initialize memory extraction agent"""
        self.model_name = os.environ.get('MEMORY_EXTRACTION_MODEL', DEFAULT_MEMORY_MODEL)
        api_key = os.environ.get('OPENROUTER_API_KEY')
        if not api_key:
            logger.error("OPENROUTER_API_KEY not set - memory extraction will fail")
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        logger.info(f"MemoryExtractor initialized with model: {self.model_name}")

    def _get_extraction_instructions(self) -> str:
        """Instructions for memory extraction - Trading focused"""
        return """Analyze this conversation and extract ONLY user-specific, actionable memories about their TRADING preferences and style.

**THE GOLDEN RULE: Extract ONLY if you can answer YES to ALL THREE:**
1. Is this SPECIFIC to this user's trading style/preferences?
2. Is this ACTIONABLE data for future trading decisions?
3. Will I need this in FUTURE conversations? (not just this session)

**Trading-Specific Categories:**
- **risk_tolerance**: User's risk appetite (conservative, moderate, aggressive, max loss per trade)
- **position_sizing**: Preferred position sizes, max portfolio allocation per stock
- **sector_preference**: Preferred sectors (IT, banking, pharma, FMCG, etc.)
- **trading_style**: Day trader, swing trader, positional, long-term investor
- **avoid_list**: Stocks or sectors user wants to avoid
- **past_learnings**: Previous trading experiences (wins, losses, lessons learned)
- **schedule**: When user trades (market open, specific hours, weekends for analysis)
- **experience_level**: Beginner, intermediate, advanced - affects explanation depth
- **communication**: Prefers detailed analysis vs quick signals, technical vs simple language

**✅ GOOD EXAMPLES (extract these):**
- "User is conservative, never risks more than 2% per trade"
- "User prefers IT and banking stocks, avoids commodities"
- "User lost money on TATAMOTORS, doesn't want to trade it again"
- "User is a swing trader, typically holds positions for 2-5 days"
- "User only trades in the first hour of market open"
- "User is a beginner, needs technical terms explained simply"
- "User's max position size is 5% of portfolio"
- "User prefers stocks with RSI below 30 for buying"

**❌ BAD EXAMPLES (DO NOT extract these):**
- "User asked for RELIANCE analysis" → Current session action
- "RELIANCE RSI is at 45" → Market data, changes constantly
- "User has ₹10 lakh in paper trading" → System already tracks this
- "User can analyze stocks" → System capability
- "NIFTY is at 22000" → Temporary market data

**STRICT FILTER RULES - NEVER extract:**
1. **System capabilities** - What the system CAN do
2. **Current market data** - Prices, indicators (they change constantly)
3. **Current session queries** - What user is analyzing RIGHT NOW
4. **Paper trading state** - Portfolio/positions (tracked by system)
5. **Generic trading facts** - "Stocks can go up or down"

**ONLY extract if it's:**
- A personal risk preference or limit
- A specific trading style or pattern
- Stocks/sectors to prefer or avoid (with reason)
- Past experiences that inform future decisions
- Timing or schedule preferences
- Communication/explanation preferences

**Confidence scoring:**
- 1.0: Explicit statement ("I never risk more than 2%", "I'm a swing trader")
- 0.8-0.9: Strong implication from repeated behavior
- 0.6-0.7: Weak implication (better to skip these)

**Target: Extract 2-8 memories per conversation, prioritizing QUALITY over quantity.**
When in doubt, DON'T extract. Better to miss a generic memory than clutter with noise.

Also provide a conversation title in the format: **[Relevant Emoji] + 3-4 words**
Examples: '📊 RELIANCE Technical Analysis', '💹 Portfolio Review Session', '🎯 Swing Trade Setup', '📈 Banking Sector Research'

**IMPORTANT: You MUST respond with valid JSON matching this exact schema:**
```json
{
  "memories": [
    {
      "fact": "string - the extracted trading preference/style",
      "category": "risk_tolerance|position_sizing|sector_preference|trading_style|avoid_list|past_learnings|schedule|experience_level|communication",
      "confidence": 0.0-1.0,
      "reasoning": "string - why this is important for future trading advice",
      "is_ephemeral": false
    }
  ],
  "summary": "string - title in format: [Emoji] + 3-4 words"
}
```"""

    def _format_conversation(self, history: List[Dict[str, str]]) -> str:
        """Format conversation history for analysis"""
        lines = []
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            # Skip system messages
            if role == 'system':
                continue

            # Format role
            role_label = {
                'user': 'User',
                'assistant': 'Nifty Strategist',
                'tool': 'Tool'
            }.get(role, role.capitalize())

            # Limit length per message to avoid token overflow
            lines.append(f"{role_label}: {content[:500]}")

        return "\n\n".join(lines)

    async def extract_memories(
        self,
        conversation_history: List[Dict[str, str]],
        conversation_id: str
    ) -> MemoryExtractionResult:
        """
        Extract memories from conversation history via OpenRouter.

        Args:
            conversation_history: List of messages with 'role' and 'content'
            conversation_id: ID of the conversation

        Returns:
            MemoryExtractionResult with extracted memories
        """
        try:
            # Format conversation for analysis
            formatted_conversation = self._format_conversation(conversation_history)

            logger.info(f"Extracting memories from conversation {conversation_id} using {self.model_name}")

            # Use json_object response format (broadly supported across OpenRouter models)
            # Unlike json_schema with strict:True, this works with most providers
            completion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_extraction_instructions()
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this conversation and extract memories:\n\n{formatted_conversation}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            # Parse JSON response - handle markdown fences some models add
            raw_response = completion.choices[0].message.content
            logger.info(f"Memory extraction raw response for {conversation_id}: {raw_response[:500]}")
            json_text = _extract_json_from_response(raw_response)
            result = MemoryExtractionResult.model_validate_json(json_text)

            logger.info(
                f"Extracted {len(result.memories)} memories from conversation {conversation_id}"
            )

            return result

        except ValidationError as e:
            logger.error(f"Memory extraction JSON parsing failed for {conversation_id}: {e}")
            return MemoryExtractionResult(
                memories=[],
                summary="Error parsing extraction result"
            )
        except Exception as e:
            logger.error(f"Memory extraction failed for conversation {conversation_id}: {e}")
            # Return empty result on error
            return MemoryExtractionResult(
                memories=[],
                summary="Error extracting memories"
            )


# Global singleton instance
_memory_extractor_instance = None

def get_memory_extractor() -> MemoryExtractor:
    """Get singleton memory extractor instance"""
    global _memory_extractor_instance
    if _memory_extractor_instance is None:
        _memory_extractor_instance = MemoryExtractor()
    return _memory_extractor_instance


def reset_memory_extractor() -> None:
    """Reset singleton (useful when env vars change)"""
    global _memory_extractor_instance
    _memory_extractor_instance = None
