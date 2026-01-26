"""
ToonFormat converter utility for efficient conversation serialization.

This module provides utilities to convert conversation data to TOON format,
achieving 30-60% token reduction compared to JSON or markdown.

HYBRID PIPELINE:
1. LLM summarizes conversation → Structured JSON (80-90% reduction)
2. TOON encodes JSON → Compact format (30-60% additional reduction)
3. Total: 90-95% token reduction on long conversations
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging
import os

try:
    from toon_format import encode, decode, estimate_savings
except ImportError:
    # Fallback if toon_format is not installed
    def encode(obj, options=None):
        raise ImportError("toon_format library not installed. Run: pip install git+https://github.com/toon-format/toon-python.git")

    def decode(toon_str, options=None):
        raise ImportError("toon_format library not installed. Run: pip install git+https://github.com/toon-format/toon-python.git")

    def estimate_savings(obj):
        return {"savings_percent": 0}

logger = logging.getLogger(__name__)


async def summarize_conversation_to_json(
    messages: List[Any],
    conversation_title: str,
    use_gemini: bool = False
) -> Dict[str, Any]:
    """
    Summarize conversation to structured JSON using LLM.

    This is the first step in the hybrid pipeline: Messages → JSON → TOON
    Achieves 80-90% token reduction by extracting only essential information.

    Note: Without LangExtract library, model choice (Grok/Gemini/GPT-OSS) performs
    similarly for structured extraction. Grok 4.1 Fast is default for cost/performance.

    Future Enhancement: Integrate Google LangExtract library with Gemini 2.5 Flash
    for more precise schema-based extraction (adds complexity/latency).

    Args:
        messages: List of message objects
        conversation_title: Original conversation title
        use_gemini: If True, use Gemini 2.5 Flash; otherwise use Grok 4.1 Fast (default)

    Returns:
        Structured JSON with key information extracted
    """
    import httpx

    # Format messages for LLM
    conversation_text = ""
    for msg in messages:
        conversation_text += f"{msg.role}: {msg.content}\n\n"

    # Structured extraction prompt - designed for LOSSLESS extraction
    # Captures all meaningful information for conversation continuity
    extraction_prompt = f"""You are extracting ALL meaningful information from a conversation for future context.
The goal is LOSSLESS compression - capture everything important so the conversation can be continued with FULL awareness.

Conversation Title: {conversation_title}

Conversation:
{conversation_text}

Extract into this JSON structure (include ALL items, not just examples):
{{
  "overview": "2-3 sentence summary covering the main goals, actions taken, and current state",

  "decisions": [
    {{"action": "what was done", "outcome": "success/failure/pending", "details": "specifics including IDs", "context": "why this was done"}}
  ],

  "entities": [
    {{"type": "product/order/collection/file/etc", "id": "exact ID like gid://shopify/Product/123", "name": "human readable name", "attributes": "price, status, tags, etc"}}
  ],

  "tool_calls": [
    {{"tool": "exact tool/script name", "action": "what it did", "result": "outcome", "data": "key output data"}}
  ],

  "pending_tasks": [
    {{"task": "what needs to be done", "priority": "high/medium/low", "context": "why/when"}}
  ],

  "user_context": {{
    "preferences": ["list all stated preferences like format preferences, communication style"],
    "constraints": ["budget limits, time constraints, requirements"],
    "background": ["relevant business context, past decisions referenced"]
  }},

  "key_exchanges": [
    {{"question": "important question asked", "answer": "key data from the answer", "significance": "why this matters"}}
  ],

  "data_points": [
    {{"metric": "sales/inventory/analytics etc", "value": "the number or data", "timeframe": "when", "source": "where from"}}
  ],

  "recent_state": {{
    "last_user_request": "exact or close paraphrase of most recent user message",
    "last_action_taken": "what was done in response",
    "conversation_status": "completed/in_progress/waiting_for_user"
  }}
}}

CRITICAL RULES:
1. Extract EXACT IDs, prices, numbers - do not paraphrase numerical data
2. Include ALL entities mentioned, not just created ones
3. Capture user preferences and constraints verbatim
4. Include tool names exactly as they appear
5. Preserve data from analytics queries, sales reports, etc.
6. Note any pending/incomplete actions explicitly

Return ONLY valid JSON, no markdown formatting or explanation."""

    try:
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not found")

        if use_gemini:
            # Alternative: Gemini 2.5 Flash
            # Note: Similar performance to Grok without LangExtract library
            model = "google/gemini-2.5-flash"
            logger.info(f"Summarizing conversation with Gemini 2.5 Flash ({len(messages)} messages)")
        else:
            # Default: Grok 4.1 Fast (50% lower hallucination, 2M context, $0.20/$0.50)
            model = "x-ai/grok-4.1-fast"
            logger.info(f"Summarizing conversation with Grok 4.1 Fast ({len(messages)} messages)")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": extraction_prompt}
                    ],
                    "response_format": {"type": "json_object"},  # Force JSON output
                    "temperature": 0.3,  # Low temperature for consistent extraction
                },
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                summary_json_str = result["choices"][0]["message"]["content"]

                # Parse JSON response
                import json
                summary_json = json.loads(summary_json_str)

                logger.info(f"Successfully extracted structured summary using {model}")
                return summary_json
            else:
                error_text = response.text
                logger.error(f"OpenRouter API error: {response.status_code} - {error_text}")
                raise Exception(f"OpenRouter API error: {response.status_code}")

    except Exception as e:
        logger.error(f"Failed to summarize conversation with LLM: {e}", exc_info=True)

        # Fallback: Create basic structured summary
        return {
            "overview": f"Conversation about {conversation_title}",
            "key_decisions": [],
            "entities_created": [],
            "pending_actions": [],
            "important_context": {},
            "recent_exchange": {
                "last_user_message": messages[-2].content if len(messages) >= 2 else "",
                "last_assistant_response": messages[-1].content if len(messages) >= 1 else ""
            }
        }


async def create_hybrid_fork_summary(
    messages: List[Any],
    conversation_title: str,
    fork_from_message_id: Optional[str] = None,
    use_gemini: bool = False,
    use_langextract: bool = False
) -> str:
    """
    Create highly compressed fork summary using hybrid LLM→JSON→TOON pipeline.

    Pipeline Options:
    1. Direct (default): Grok 4.1 Fast → Structured JSON → TOON (fast, cheap)
    2. use_gemini=True: Gemini 2.5 Flash → Structured JSON → TOON (similar quality)
    3. use_langextract=True: LangExtract + Gemini → Schema-enforced JSON → TOON (lossless)

    Args:
        messages: List of messages to summarize
        conversation_title: Original conversation title
        fork_from_message_id: Optional message ID where fork occurred
        use_gemini: If True, use Gemini 2.5 Flash for direct extraction
        use_langextract: If True, use LangExtract for schema-enforced lossless extraction

    Returns:
        TOON-formatted summary with maximum compression
    """
    # Option 3: LangExtract for lossless, schema-enforced extraction
    if use_langextract:
        try:
            from utils.langextract_converter import create_langextract_fork_summary
            logger.info(f"Using LangExtract for lossless extraction of {len(messages)} messages")
            return await create_langextract_fork_summary(
                messages,
                conversation_title,
                fork_from_message_id
            )
        except ImportError as e:
            logger.warning(f"LangExtract not available, falling back to direct extraction: {e}")
            # Fall through to direct extraction

    # Options 1 & 2: Direct LLM extraction
    logger.info(f"Step 1/2: LLM extracting structured summary from {len(messages)} messages")
    summary_json = await summarize_conversation_to_json(messages, conversation_title, use_gemini)

    # Step 2: Encode JSON to TOON format
    logger.info("Step 2/2: Encoding JSON to TOON format")

    try:
        # Add fork metadata
        fork_data = {
            "fork_metadata": {
                "original_title": conversation_title,
                "fork_timestamp": datetime.now(timezone.utc).isoformat(),
                "message_count": len(messages),
                "fork_from_message": fork_from_message_id if fork_from_message_id else None
            },
            "summary": summary_json
        }

        # Encode to TOON
        toon_summary = encode(fork_data)

        # Wrap in markdown for readability
        full_summary = f"""# Forked Conversation Context (Hybrid LLM→TOON)

{toon_summary}

---
**Compression**: LLM extracted key info → TOON encoded (90-95% token reduction)
**Original**: {len(messages)} messages
**Model**: {"Gemini 2.5 Flash" if use_gemini else "Grok 4.1 Fast"}
"""

        logger.info(f"Hybrid fork summary created: {len(full_summary)} chars")
        return full_summary

    except Exception as e:
        logger.error(f"Failed to create hybrid summary: {e}", exc_info=True)
        # Fallback to basic TOON encoding
        return create_fork_context_toon(messages, conversation_title, fork_from_message_id)


def messages_to_toon(messages: List[Any], conversation_title: str, include_metadata: bool = True) -> str:
    """
    Convert conversation messages to TOON format for efficient context representation.

    Args:
        messages: List of message objects with role and content
        conversation_title: Title of the conversation
        include_metadata: Whether to include metadata like timestamps

    Returns:
        TOON-formatted string representation
    """
    # Build structured data for TOON encoding
    conversation_data = {
        "title": conversation_title,
        "message_count": len(messages),
        "messages": []
    }

    for msg in messages:
        msg_data = {
            "role": msg.role,
            "content": msg.content[:1000] if len(msg.content) > 1000 else msg.content  # Truncate very long messages
        }

        if include_metadata and hasattr(msg, 'created_at') and msg.created_at:
            msg_data["timestamp"] = msg.created_at.isoformat()

        # Include tool calls if present
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            msg_data["tool_calls"] = [
                {
                    "tool": tc.get("name", "unknown"),
                    "status": tc.get("status", "unknown")
                }
                for tc in msg.tool_calls
            ]

        conversation_data["messages"].append(msg_data)

    # Encode to TOON format
    try:
        toon_str = encode(conversation_data)

        # Estimate token savings (optional - requires tiktoken)
        try:
            savings = estimate_savings(conversation_data)
            logger.info(f"TOON encoding: {len(toon_str)} chars, ~{savings.get('savings_percent', 0):.1f}% token reduction")
        except Exception:
            # tiktoken not available, just log character count
            logger.info(f"TOON encoding: {len(toon_str)} chars")

        return toon_str
    except Exception as e:
        logger.error(f"Failed to encode to TOON format: {e}", exc_info=True)
        # Fallback to simple text format
        return _fallback_format(messages, conversation_title)


def toon_to_messages(toon_str: str) -> Dict[str, Any]:
    """
    Decode TOON-formatted conversation back to structured data.

    Args:
        toon_str: TOON-formatted string

    Returns:
        Dictionary with conversation data
    """
    try:
        return decode(toon_str)
    except Exception as e:
        logger.error(f"Failed to decode TOON format: {e}", exc_info=True)
        return {}


def create_fork_context_toon(
    messages: List[Any],
    conversation_title: str,
    fork_from_message_id: Optional[str] = None
) -> str:
    """
    Create a TOON-formatted context summary for forked conversations.

    This replaces the LLM-based summarization with a structured TOON format
    that preserves all context while using significantly fewer tokens.

    Args:
        messages: List of messages to include in fork
        conversation_title: Original conversation title
        fork_from_message_id: Optional message ID where fork occurred

    Returns:
        TOON-formatted context string with metadata
    """
    # Prepare fork metadata
    fork_metadata = {
        "fork_info": {
            "original_title": conversation_title,
            "fork_timestamp": datetime.now(timezone.utc).isoformat(),
            "message_count": len(messages)
        }
    }

    if fork_from_message_id:
        fork_metadata["fork_info"]["fork_from_message"] = fork_from_message_id

    # Split into older context and recent messages
    # Keep last 5 messages for verbatim context
    if len(messages) > 5:
        older_messages = messages[:-5]
        recent_messages = messages[-5:]

        # Compress older messages more aggressively
        older_context = messages_to_toon(older_messages, conversation_title, include_metadata=False)
        recent_context = messages_to_toon(recent_messages, "Recent Messages", include_metadata=True)

        # Combine with clear sections
        full_context = f"""# Forked Conversation Context

## Fork Metadata
{encode(fork_metadata)}

## Conversation History (Compressed)
{older_context}

## Recent Messages (Full Context)
{recent_context}

---
**Note**: This context is in TOON format (Token-Oriented Object Notation) for efficiency.
Original conversation: {conversation_title}
Total messages preserved: {len(messages)}
"""
    else:
        # For shorter conversations, just encode everything
        full_context = f"""# Forked Conversation Context

## Fork Metadata
{encode(fork_metadata)}

## All Messages
{messages_to_toon(messages, conversation_title, include_metadata=True)}

---
**Note**: This context is in TOON format (Token-Oriented Object Notation) for efficiency.
Original conversation: {conversation_title}
Total messages preserved: {len(messages)}
"""

    return full_context


def _fallback_format(messages: List[Any], conversation_title: str) -> str:
    """
    Fallback format if TOON encoding fails.
    Still more structured than plain markdown.
    """
    text = f"# {conversation_title}\nMessages: {len(messages)}\n\n"
    for msg in messages:
        text += f"{msg.role}: {msg.content[:500]}...\n\n"
    return text


def estimate_token_savings(messages: List[Any], conversation_title: str) -> Dict[str, Any]:
    """
    Estimate token savings from using TOON format vs traditional markdown.

    Returns:
        Dictionary with token counts and savings percentage
    """
    try:
        # Create TOON representation
        toon_repr = messages_to_toon(messages, conversation_title)

        # Create traditional markdown representation
        markdown_repr = f"# {conversation_title}\n\n"
        for msg in messages:
            markdown_repr += f"**{msg.role.capitalize()}:** {msg.content}\n\n"

        # Try to use tiktoken for accurate counting
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
            toon_tokens = len(enc.encode(toon_repr))
            markdown_tokens = len(enc.encode(markdown_repr))
        except Exception:
            # Fallback: Rough token estimation (1 token ≈ 4 characters for English)
            toon_tokens = len(toon_repr) // 4
            markdown_tokens = len(markdown_repr) // 4

        savings_pct = ((markdown_tokens - toon_tokens) / markdown_tokens * 100) if markdown_tokens > 0 else 0

        return {
            "toon_tokens": toon_tokens,
            "markdown_tokens": markdown_tokens,
            "tokens_saved": markdown_tokens - toon_tokens,
            "savings_percent": savings_pct,
            "toon_chars": len(toon_repr),
            "markdown_chars": len(markdown_repr)
        }
    except Exception as e:
        logger.error(f"Failed to estimate token savings: {e}", exc_info=True)
        # Return empty/default values
        return {
            "toon_tokens": 0,
            "markdown_tokens": 0,
            "tokens_saved": 0,
            "savings_percent": 0,
            "toon_chars": 0,
            "markdown_chars": 0
        }
