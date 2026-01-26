"""
Memory Extraction Agent - Uses Grok 4 Fast for memory extraction

This agent:
1. Reviews entire conversation history
2. Identifies facts, preferences, and context using LLM
3. Categorizes memories appropriately
4. Returns structured memory objects with embeddings

Uses Grok 4 Fast (2M context) via OpenRouter for fast, smart extraction.
"""

import os
import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


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


class MemoryExtractor:
    """
    Agent that extracts memories from conversation history using Grok 4 Fast

    Uses Grok 4.1 Fast (2M context, fast inference) via OpenRouter.
    Leverages JSON mode with Pydantic parsing for structured extraction.
    """

    def __init__(self):
        """Initialize memory extraction agent"""
        # Use Grok 4.1 Fast for extraction (fast, smart, 2M context)
        self.model_name = "x-ai/grok-4.1-fast"
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get('OPENROUTER_API_KEY')
        )

    def _get_extraction_instructions(self) -> str:
        """Instructions for memory extraction"""
        return """Analyze this conversation and extract ONLY user-specific, actionable memories.

**THE GOLDEN RULE: Extract ONLY if you can answer YES to ALL THREE:**
1. Is this SPECIFIC to this user? (not generic business info)
2. Is this ACTIONABLE data I'll need? (IDs, credentials, unique preferences)
3. Will I need this in FUTURE conversations? (not just this session)

**Categories:**
- **fact**: User-specific data (account IDs, API keys, unique URLs, specific contact info)
- **preference**: User's personal preferences (notification times, preferred tools, workflow styles)
- **context**: User-specific context (timezone, role, team structure, busy seasons)
- **task**: Ongoing goals or projects (launch dates, active campaigns, tracked metrics)

**✅ GOOD EXAMPLES (extract these):**
- "User's Google Ads customer ID is 522-285-1423"
- "User's Shopify store URL is mystore.myshopify.com"
- "User's team lead is John (john@company.com)"
- "The large homepage banner image is 1609x902 px on iDrinkCoffee.com"

**❌ BAD EXAMPLES (DO NOT extract these):**
- "User employs a marketing agent" → System already knows its own capabilities
- "System integrates with Google Ads" → System capability, not user data
- "User's business sells coffee products" → Generic, obvious from context
- "User's business uses Shopify" → Generic platform info
- "User can analyze sales data" → System feature, not user-specific

**STRICT FILTER RULES - NEVER extract:**
1. **System capabilities** - What the system CAN do (agents, APIs, integrations)
2. **Generic business info** - Industry, platform used, product category (unless VERY specific)
3. **Current session actions** - What user is doing RIGHT NOW
4. **Temporary data** - File paths, test values, one-time queries
5. **Database content** - Products, orders, prices (already in DB)
6. **Obvious context** - Things you can infer from the conversation every time

**ONLY extract if it's:**
- A specific ID, credential, or account number
- A unique preference or workflow detail
- A contact, person, or team member
- A specific goal, project, or tracked item
- Something you CAN'T infer from context each time

**Confidence scoring:**
- 1.0: Explicit statement ("My customer ID is X", "I prefer Y")
- 0.8-0.9: Strong implication from repeated behavior
- 0.6-0.7: Weak implication (better to skip these)

**Target: Extract 2-8 memories per conversation, prioritizing QUALITY over quantity.**
When in doubt, DON'T extract. Better to miss a generic memory than clutter the database.

Also provide a conversation title in the format: **[Relevant Emoji] + 3-4 words**
Examples: '☕ Coffee Equipment Setup', '💰 Pricing Strategy Discussion', '📧 Email System Check', '🔍 Deepseek Vision Research'

**IMPORTANT: You MUST respond with valid JSON matching this exact schema:**
```json
{
  "memories": [
    {
      "fact": "string - the extracted user-specific fact",
      "category": "fact|preference|context|task",
      "confidence": 0.0-1.0,
      "reasoning": "string - why this specific user data is important",
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
                'assistant': 'EspressoBot',
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
        Extract memories from conversation history using LangExtract

        Args:
            conversation_history: List of messages with 'role' and 'content'
            conversation_id: ID of the conversation

        Returns:
            MemoryExtractionResult with extracted memories
        """
        try:
            # Format conversation for analysis
            formatted_conversation = self._format_conversation(conversation_history)

            # Build extraction prompt with instructions
            full_prompt = f"""{self._get_extraction_instructions()}

---

**Conversation to analyze:**

{formatted_conversation}"""

            logger.info(f"Extracting memories from conversation {conversation_id} using Grok 4 Fast")

            # Get Pydantic schema as JSON schema
            schema = MemoryExtractionResult.model_json_schema()

            # Use Grok 4 Fast with structured outputs via OpenRouter
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
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "memory_extraction",
                        "strict": True,
                        "schema": schema
                    }
                },
                temperature=0.3  # Lower temperature for more consistent extraction
            )

            # Parse JSON response into Pydantic model
            json_response = completion.choices[0].message.content
            result = MemoryExtractionResult.model_validate_json(json_response)

            logger.info(
                f"Extracted {len(result.memories)} memories from conversation {conversation_id}"
            )

            return result

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
