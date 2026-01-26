"""
Memory Extraction using LangExtract - Structured extraction with few-shot learning

This agent:
1. Uses langextract for structured memory extraction
2. Provides few-shot examples for quality control
3. Generates normalized/rephrased memories for better semantic search
4. Filters out ephemeral/task-specific content
5. Returns memories with confidence scores and metadata

Based on ebot's successful implementation with improvements for semantic search.
"""

import os
import json
import logging
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import langextract as lx

logger = logging.getLogger(__name__)


class ExtractedMemory(BaseModel):
    """A single extracted memory with metadata"""
    fact: str = Field(description="The extracted fact - normalized for semantic search")
    original_text: str = Field(description="Original text from conversation")
    category: str = Field(description="Category: fact, preference, context, task")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Why this memory is important")
    is_ephemeral: bool = Field(default=False, description="True if task-specific/temporary")


class MemoryExtractionResult(BaseModel):
    """Result of langextract memory extraction"""
    memories: List[ExtractedMemory] = Field(default_factory=list)
    summary: str = Field(description="Brief 2-4 word conversation title describing the topic")


class LangExtractMemoryExtractor:
    """
    Memory extractor using langextract for structured, high-quality extraction

    Uses few-shot learning with examples to ensure:
    - Proper memory normalization for semantic search
    - Filtering of ephemeral/task-specific content
    - Structured attributes for better retrieval
    """

    def __init__(self, model_id: str = "gemini-2.5-flash-preview-09-2025"):
        """
        Initialize langextract memory extractor

        Args:
            model_id: Model to use (default: gemini-2.5-flash-preview-09-2025 - latest Gemini Flash)
                     Also supports: gpt-4.1-nano, gpt-5, deepseek/deepseek-v3.1-terminus (via OpenRouter), etc.
        """
        self.model_id = model_id

    def _get_extraction_examples(self) -> List[lx.data.ExampleData]:
        """
        Few-shot examples showing good memory extraction patterns

        IMPORTANT: Uses completely fictional examples that can't match real user data
        to prevent LLM from extracting example content as actual memories.

        Reduced to 2 examples for faster alignment processing.
        """
        return [
            lx.data.ExampleData(
                text="User: My name is Zara and I run a pottery studio in Wellington. We specialize in ceramic tableware.",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="user_fact",
                        extraction_text="My name is Zara",
                        attributes={
                            "fact": "The user's name is Zara",
                            "original_text": "My name is Zara",
                            "category": "fact",
                            "confidence": 1.0,
                            "reasoning": "Explicit user identity",
                            "is_ephemeral": False
                        }
                    ),
                    lx.data.Extraction(
                        extraction_class="user_fact",
                        extraction_text="I run a pottery studio in Wellington",
                        attributes={
                            "fact": "User runs a pottery studio in Wellington",
                            "original_text": "I run a pottery studio in Wellington",
                            "category": "fact",
                            "confidence": 1.0,
                            "reasoning": "Business and location info",
                            "is_ephemeral": False
                        }
                    )
                ]
            ),
            lx.data.ExampleData(
                text="User: I manage my email with Evolution mail client.\nAssistant: Got it, I'll remember that.\nUser: And I use Thunderbird for work emails.",
                extractions=[
                    # Extract persistent tools/systems - NOT ephemeral
                    lx.data.Extraction(
                        extraction_class="user_fact",
                        extraction_text="I manage my email with Evolution mail client",
                        attributes={
                            "fact": "User manages email with Evolution mail client",
                            "original_text": "I manage my email with Evolution mail client",
                            "category": "fact",
                            "confidence": 1.0,
                            "reasoning": "Persistent tool user has installed",
                            "is_ephemeral": False  # Tools/systems are NOT ephemeral!
                        }
                    ),
                    lx.data.Extraction(
                        extraction_class="user_fact",
                        extraction_text="I use Thunderbird for work emails",
                        attributes={
                            "fact": "User uses Thunderbird for work emails",
                            "original_text": "I use Thunderbird for work emails",
                            "category": "fact",
                            "confidence": 1.0,
                            "reasoning": "Persistent tool for specific purpose",
                            "is_ephemeral": False  # Tools/systems are NOT ephemeral!
                        }
                    )
                ]
            )
        ]

    def _get_prompt_description(self) -> str:
        """Prompt for langextract describing extraction task"""
        return """Extract long-term memories from the REAL USER CONVERSATION ONLY.

⚠️⚠️⚠️ CRITICAL INSTRUCTION - READ CAREFULLY ⚠️⚠️⚠️

The examples above are FICTIONAL TRAINING DATA for teaching you the extraction pattern.
They are about a FAKE pottery business and contain COMPLETELY MADE-UP information.

🚫 ABSOLUTELY DO NOT extract ANY of the following from the examples:
   - Names like "Zara"
   - Locations like "Wellington"
   - Business types like "pottery studio" or "ceramic tableware"
   - Technical details like "1200 degrees", "cone 6", "lead-free glazes", "kiln door sensor"
   - Operations like "quality checks on Tuesdays" or anything about scheduling
   - ANY other facts from the example conversations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          END OF EXAMPLES - START OF REAL USER CONVERSATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ ONLY extract facts from the ACTUAL USER CONVERSATION below.
✅ Ignore everything in the examples above - they are fictional training data only.

If you extract ANYTHING from the examples above, you have completely failed this task.

CRITICAL PRINCIPLES:
1. **Normalize for Questions**: Rephrase as declarative statements that answer questions
   - Input: "My name is John" → Output: "The user's name is John"
   - Input: "I love coffee" → Output: "User loves coffee"
   - This helps semantic search match questions to answers!

2. **Be Specific**: Extract concrete details, not vague categories
   ✓ "User's Shopify store is idrinkcoffee.myshopify.com"
   ✗ "User has a store" (too vague)

3. **Filter Ephemeral Content**: Mark ONLY one-time tasks/temporary info as ephemeral=true

   EPHEMERAL (mark is_ephemeral=true):
   - One-time tasks: "Update price today", "Check order #123", "Send email now"
   - Temporary files: "wholesale-prices-2025.csv", "test-data.json"
   - Current operations: "Working on product launch", "Debugging issue"
   - Specific requests: "Show me sales for yesterday"

   NOT EPHEMERAL (mark is_ephemeral=false):
   - Tools/systems user has: "User uses notmuch for email", "User has bash access"
   - Business domain: "User sells coffee equipment", "User operates Shopify store"
   - Preferences: "User prefers dark mode", "User checks email daily"
   - Capabilities: "Assistant can execute bash commands"
   - Ongoing practices: "User monitors competitor pricing weekly"

4. **Long-term Value**: Extract facts about systems, tools, preferences, and business - NOT one-time requests
   ✓ "User manages email with notmuch" (persistent system)
   ✓ "User sells coffee equipment" (business domain)
   ✓ "User has bash access" (persistent capability)
   ✗ "User needs sales report by 3pm" (one-time deadline)

CONFIDENCE SCORING:
- 1.0: Explicit user statement ("I am...", "My store is...")
- 0.9: Strong contextual evidence
- 0.7-0.8: Moderate implication
- <0.7: Weak assumption (usually skip these)

CATEGORIES:
- fact: Factual information (name, store URL, business type)
- preference: User preferences (tools, workflows, communication style)
- context: Background info (timezone, busy season, team structure)
- task: Ongoing goals/monitoring (NOT one-time tasks!)

Extract 1-5 high-quality memories MAXIMUM. Quality over quantity!
Be VERY selective - only extract truly valuable long-term information.
Most conversations should yield 1-3 memories, not more.

**CONVERSATION TITLE** (REQUIRED):
You MUST also extract exactly ONE title for this conversation:
- Extraction class: "title"
- Format: [Emoji] + 3-4 words
- Use relevant emoji that represents the topic
- Make it instantly recognizable for quick scanning
- Examples:
  ✓ "☕ Coffee Equipment Setup"
  ✓ "💰 Pricing Strategy Discussion"
  ✓ "📦 Product Variants Preference"
  ✓ "🏪 Store Configuration Help"
  ✓ "📊 Analytics Review Session"

Extract the title as a separate extraction with class "title".
"""

    async def _generate_conversation_title(self, conversation_text: str) -> str:
        """Generate emoji + 3-4 word title for conversation (fallback only)"""
        import google.generativeai as genai

        try:
            # Fallback title generation using Gemini Flash directly (rarely used since langextract extracts titles)
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-2.5-flash-preview-09-2025")

            prompt = f"""Generate a brief conversation title. Format: [Relevant Emoji] + 3-4 words.
Examples: '☕ Coffee Equipment Setup', '💰 Pricing Strategy Discussion', '📦 Product Management Tips'

Create a title for this conversation:

{conversation_text[:1000]}"""

            response = await model.generate_content_async(prompt)
            title = response.text.strip()
            logger.info(f"[Title] Generated (fallback): {title}")
            return title

        except Exception as e:
            logger.error(f"Failed to generate title: {e}")
            return "💬 General Discussion"

    async def extract_memories(
        self,
        conversation_text: str,
        user_id: str
    ) -> MemoryExtractionResult:
        """
        Extract memories from conversation using langextract

        Args:
            conversation_text: Formatted conversation history
            user_id: User identifier

        Returns:
            MemoryExtractionResult with extracted memories
        """
        try:
            # Detect model provider and configure accordingly
            is_openai = self.model_id.startswith("gpt") or "gpt-" in self.model_id
            is_openrouter = "/" in self.model_id and "google/" not in self.model_id  # OpenRouter (but not google/)
            is_gpt5 = "gpt-5" in self.model_id
            is_gemini = "gemini" in self.model_id.lower() or "google/" in self.model_id

            # Configure API key
            if is_gemini:
                # Gemini uses GEMINI_API_KEY - langextract has native Gemini support
                api_key = os.getenv("GEMINI_API_KEY")
                logger.info(f"Using Google Gemini natively with model: {self.model_id}")
            elif is_openrouter:
                api_key = os.getenv("OPENROUTER_API_KEY")
                logger.info(f"Using OpenRouter with model: {self.model_id}")
            elif is_openai:
                api_key = os.getenv("OPENAI_API_KEY")
                logger.info(f"Using OpenAI with model: {self.model_id}")
            else:
                api_key = None

            logger.info(f"[EXTRACT START] Extracting memories using langextract with {self.model_id}")

            # Configure extraction parameters
            # Use fictional examples that can't match real user data
            extract_params = {
                "text_or_documents": conversation_text,
                "prompt_description": self._get_prompt_description(),
                "examples": self._get_extraction_examples(),
                "model_id": self.model_id,
                "api_key": api_key,
                "fence_output": True,  # Use markdown fences for JSON
                "use_schema_constraints": False,  # Better compatibility
                "extraction_passes": 1,  # Single pass for speed (default is 2)
                "max_workers": 1,  # Single batch processing
                "max_char_buffer": 50000,  # Large buffer = single batch for most conversations
                "debug": False,  # Disable debug output
            }

            # Add language_model_params for OpenRouter only
            if is_openrouter:
                extract_params["language_model_params"] = {
                    "base_url": "https://openrouter.ai/api/v1"
                }

            # GPT-5 and Gemini only accept default temperature
            if not is_gpt5 and not is_gemini:
                extract_params["temperature"] = 0.1

            # Run langextract in thread pool (it's synchronous)
            logger.info(f"[LX CALL START] Calling lx.extract() now...")
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    lambda: lx.extract(**extract_params)
                )
            logger.info(f"[LX CALL END] lx.extract() completed")

            # Parse results into structured memories
            memories = []
            filtered_count = 0
            title_from_extraction = None  # Check if langextract returned a title

            if result and hasattr(result, 'extractions') and result.extractions:
                for extraction in result.extractions:
                    attrs = extraction.attributes or {}

                    # Check if this extraction contains a title
                    if extraction.extraction_class == "title" or "title" in attrs:
                        title_from_extraction = attrs.get("title") or extraction.extraction_text
                        logger.info(f"[TITLE] Found title in extraction: {title_from_extraction}")
                        continue  # Don't store title as a memory

                    # Skip ephemeral memories
                    if attrs.get("is_ephemeral", False):
                        filtered_count += 1
                        logger.info(f"✗ Filtered (ephemeral): {attrs.get('fact', extraction.extraction_text)[:60]}...")
                        continue

                    # Skip low confidence
                    confidence = float(attrs.get("confidence", 0.5))
                    if confidence < 0.6:
                        filtered_count += 1
                        logger.info(f"✗ Filtered (low confidence {confidence}): {attrs.get('fact', extraction.extraction_text)[:60]}...")
                        continue

                    # Extract normalized fact (prioritize over original)
                    fact = attrs.get("fact") or extraction.extraction_text
                    if not fact or len(fact.strip()) < 10:
                        filtered_count += 1
                        continue

                    memory = ExtractedMemory(
                        fact=fact.strip(),
                        original_text=attrs.get("original_text", extraction.extraction_text or ""),
                        category=attrs.get("category", "fact"),
                        confidence=confidence,
                        reasoning=attrs.get("reasoning", "Extracted from conversation"),
                        is_ephemeral=False
                    )
                    memories.append(memory)

                    logger.info(f"✓ Extracted: {memory.fact[:60]}... (confidence: {confidence})")

            logger.info(f"Extracted {len(memories)} memories (filtered {filtered_count} ephemeral/low-quality)")

            # Use title from extraction if available, otherwise generate one
            if title_from_extraction:
                title_summary = title_from_extraction
                logger.info(f"[TITLE] Using title from langextract: {title_summary}")
            else:
                logger.info(f"[TITLE CALL START] No title in extraction, generating one...")
                title_summary = await self._generate_conversation_title(conversation_text)
                logger.info(f"[TITLE CALL END] Title generation completed: {title_summary}")

            return MemoryExtractionResult(
                memories=memories,
                summary=title_summary
            )

        except Exception as e:
            logger.error(f"LangExtract extraction failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Return empty result rather than failing
            return MemoryExtractionResult(
                memories=[],
                summary="Memory extraction failed"
            )


# Global instance
_extractor_instance: Optional[LangExtractMemoryExtractor] = None

def get_langextract_memory_extractor(model_id: str = "gemini-2.5-flash-preview-09-2025") -> LangExtractMemoryExtractor:
    """Get or create langextract memory extractor instance"""
    global _extractor_instance
    if _extractor_instance is None or _extractor_instance.model_id != model_id:
        _extractor_instance = LangExtractMemoryExtractor(model_id=model_id)
    return _extractor_instance
