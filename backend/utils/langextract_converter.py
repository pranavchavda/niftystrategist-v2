"""
LangExtract-based conversation compression for lossless summarization.

This module uses Google's LangExtract library with Gemini 2.5 Flash to extract
structured information from conversations with source grounding (character-level
precision for traceability).

Key Benefits over Direct Prompt Extraction:
1. Schema enforcement - Guaranteed structured output
2. Source grounding - Every fact traced to original text
3. Few-shot learning - Consistent extraction patterns
4. Long-context optimization - Handles very long conversations

Pipeline:
Messages → LangExtract (Gemini) → Grounded JSON → TOON → Minimal tokens
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

try:
    import langextract as lx
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False
    lx = None

try:
    from toon_format import encode
except ImportError:
    def encode(obj, options=None):
        import json
        return json.dumps(obj, indent=2)

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMA DEFINITION: What to extract for "lossless" conversation compression
# =============================================================================

EXTRACTION_PROMPT = """
Extract ALL meaningful information from this conversation for future context.
The goal is LOSSLESS compression - capture everything important so the
conversation can be continued with full awareness.

Extract these entity types:
1. DECISION - Any decision made, action taken, or outcome reached
2. ENTITY - Products, orders, IDs, files, or objects created/referenced
3. TASK - Pending actions, follow-ups, or incomplete work
4. CONTEXT - User preferences, constraints, requirements, background info
5. EXCHANGE - Key question-answer pairs that matter for continuity
6. TOOL_CALL - Any tool/function that was called with its result

Use EXACT text from the conversation. Include attributes to capture the full meaning.
Extract in chronological order of appearance.
"""

# Few-shot examples to teach LangExtract the extraction pattern
EXTRACTION_EXAMPLES = [
    # Example 1: Product creation workflow
    {
        "text": """user: I need to create a new product for the Breville Bambino Plus espresso machine at $299

assistant: I'll create that product for you using create_full_product.py.

The product has been created successfully:
- Product ID: gid://shopify/Product/8234567890
- Title: Breville Bambino Plus
- Price: $299.00
- Tags: espresso, breville, compact

user: Great! Can you also add it to the Home Espresso collection?

assistant: Done! I've added the product to the Home Espresso collection.""",
        "extractions": [
            {
                "class": "DECISION",
                "text": "create a new product for the Breville Bambino Plus espresso machine at $299",
                "attributes": {
                    "action": "product_creation",
                    "outcome": "success",
                    "details": "Breville Bambino Plus at $299"
                }
            },
            {
                "class": "TOOL_CALL",
                "text": "create_full_product.py",
                "attributes": {
                    "tool": "create_full_product.py",
                    "status": "success",
                    "result": "Product created"
                }
            },
            {
                "class": "ENTITY",
                "text": "gid://shopify/Product/8234567890",
                "attributes": {
                    "type": "product",
                    "title": "Breville Bambino Plus",
                    "price": "$299.00",
                    "tags": "espresso, breville, compact"
                }
            },
            {
                "class": "DECISION",
                "text": "add it to the Home Espresso collection",
                "attributes": {
                    "action": "collection_add",
                    "outcome": "success",
                    "collection": "Home Espresso"
                }
            }
        ]
    },
    # Example 2: Analytics and preferences
    {
        "text": """user: What were our sales yesterday? I prefer seeing data in a table format.

assistant: Let me query the analytics for yesterday's sales using ShopifyQL.

Here are yesterday's sales:
| Product | Units | Revenue |
|---------|-------|---------|
| Bambino Plus | 12 | $3,588 |
| Oracle Touch | 3 | $7,497 |

Total: $11,085 from 15 orders.

user: Nice! Can you also check if we have any low inventory items?""",
        "extractions": [
            {
                "class": "CONTEXT",
                "text": "I prefer seeing data in a table format",
                "attributes": {
                    "type": "user_preference",
                    "preference": "table_format_for_data"
                }
            },
            {
                "class": "TOOL_CALL",
                "text": "query the analytics for yesterday's sales using ShopifyQL",
                "attributes": {
                    "tool": "analytics.py",
                    "query_type": "sales",
                    "timeframe": "yesterday"
                }
            },
            {
                "class": "EXCHANGE",
                "text": "Total: $11,085 from 15 orders",
                "attributes": {
                    "question": "sales yesterday",
                    "answer": "$11,085 from 15 orders",
                    "key_data": "Bambino Plus: 12 units, Oracle Touch: 3 units"
                }
            },
            {
                "class": "TASK",
                "text": "check if we have any low inventory items",
                "attributes": {
                    "status": "pending",
                    "action": "inventory_check",
                    "priority": "normal"
                }
            }
        ]
    }
]


def _build_langextract_examples() -> List:
    """Convert our example format to LangExtract's ExampleData format."""
    if not LANGEXTRACT_AVAILABLE:
        return []

    examples = []
    for ex in EXTRACTION_EXAMPLES:
        extractions = []
        for ext in ex["extractions"]:
            extractions.append(
                lx.data.Extraction(
                    extraction_class=ext["class"],
                    extraction_text=ext["text"],
                    attributes=ext["attributes"]
                )
            )
        examples.append(
            lx.data.ExampleData(
                text=ex["text"],
                extractions=extractions
            )
        )
    return examples


async def extract_with_langextract(
    messages: List[Any],
    conversation_title: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract structured information from conversation using LangExtract.

    This provides more precise, schema-enforced extraction with source grounding
    compared to direct prompt-based extraction.

    Args:
        messages: List of message objects with role and content
        conversation_title: Title of the conversation
        api_key: Optional Gemini API key (defaults to env var)

    Returns:
        Structured extraction with source grounding
    """
    if not LANGEXTRACT_AVAILABLE:
        raise ImportError(
            "langextract not installed. Run: pip install langextract"
        )

    # Format conversation as text
    conversation_text = f"# Conversation: {conversation_title}\n\n"
    for msg in messages:
        role = msg.role.upper()
        conversation_text += f"{role}: {msg.content}\n\n"

    # Get API key
    gemini_api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LANGEXTRACT_API_KEY")
    if not gemini_api_key:
        raise ValueError(
            "Gemini API key required. Set GEMINI_API_KEY or LANGEXTRACT_API_KEY environment variable."
        )

    logger.info(f"Running LangExtract on {len(messages)} messages ({len(conversation_text)} chars)")

    try:
        # Build examples
        examples = _build_langextract_examples()

        # Run extraction with Gemini 2.5 Flash (matching Replit's working config)
        # NOTE: Using defaults for max_workers/max_char_buffer - our overrides caused issues
        result = lx.extract(
            text_or_documents=conversation_text,
            prompt_description=EXTRACTION_PROMPT,
            examples=examples,
            model_id="gemini-2.5-flash",  # Standard Flash (not Lite)
            api_key=gemini_api_key,
            extraction_passes=1,  # Single pass
        )

        # Parse extractions into structured format
        extractions_by_class = {
            "decisions": [],
            "entities": [],
            "tasks": [],
            "context": [],
            "exchanges": [],
            "tool_calls": []
        }

        class_mapping = {
            "DECISION": "decisions",
            "ENTITY": "entities",
            "TASK": "tasks",
            "CONTEXT": "context",
            "EXCHANGE": "exchanges",
            "TOOL_CALL": "tool_calls"
        }

        if hasattr(result, 'extractions') and result.extractions:
            for ext in result.extractions:
                class_key = class_mapping.get(ext.extraction_class)
                if class_key:
                    extraction_dict = {
                        "text": ext.extraction_text,
                        "attributes": ext.attributes or {},
                    }
                    # Include source grounding if available
                    if hasattr(ext, 'start_char') and ext.start_char is not None:
                        extraction_dict["source"] = {
                            "start": ext.start_char,
                            "end": ext.end_char
                        }
                    extractions_by_class[class_key].append(extraction_dict)

        # Build final structured output
        structured_output = {
            "metadata": {
                "title": conversation_title,
                "message_count": len(messages),
                "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
                "extractor": "langextract_gemini_2.5_flash",
                "source_grounded": True
            },
            "extractions": extractions_by_class,
            "summary": {
                "total_decisions": len(extractions_by_class["decisions"]),
                "total_entities": len(extractions_by_class["entities"]),
                "pending_tasks": len([t for t in extractions_by_class["tasks"]
                                     if t.get("attributes", {}).get("status") == "pending"]),
                "context_items": len(extractions_by_class["context"]),
                "key_exchanges": len(extractions_by_class["exchanges"]),
                "tool_calls": len(extractions_by_class["tool_calls"])
            }
        }

        logger.info(
            f"LangExtract completed: {structured_output['summary']['total_decisions']} decisions, "
            f"{structured_output['summary']['total_entities']} entities, "
            f"{structured_output['summary']['pending_tasks']} pending tasks"
        )

        return structured_output

    except Exception as e:
        logger.error(f"LangExtract extraction failed: {e}", exc_info=True)
        raise


async def create_langextract_fork_summary(
    messages: List[Any],
    conversation_title: str,
    fork_from_message_id: Optional[str] = None,
    api_key: Optional[str] = None
) -> str:
    """
    Create highly compressed, lossless fork summary using LangExtract + TOON.

    Pipeline:
    1. LangExtract (Gemini 2.5 Flash) → Schema-enforced JSON with source grounding
    2. TOON encoding → Compact format
    3. Result: Lossless compression with full traceability

    Args:
        messages: List of messages to summarize
        conversation_title: Original conversation title
        fork_from_message_id: Optional message ID where fork occurred
        api_key: Optional Gemini API key

    Returns:
        TOON-formatted summary with source-grounded extractions
    """
    logger.info(f"Creating LangExtract fork summary for {len(messages)} messages")

    # Step 1: Extract with LangExtract
    extraction_result = await extract_with_langextract(
        messages,
        conversation_title,
        api_key
    )

    # Step 2: Add fork metadata
    fork_data = {
        "fork_metadata": {
            "original_title": conversation_title,
            "fork_timestamp": datetime.now(timezone.utc).isoformat(),
            "message_count": len(messages),
            "fork_from_message": fork_from_message_id,
            "extraction_method": "langextract_gemini_2.5_flash",
            "source_grounded": True
        },
        "extraction": extraction_result["extractions"],
        "summary": extraction_result["summary"]
    }

    # Step 3: Encode to TOON
    toon_output = encode(fork_data)

    # Wrap with header
    full_summary = f"""# Forked Conversation Context (LangExtract + TOON)

{toon_output}

---
**Extraction**: LangExtract with Gemini 2.5 Flash (schema-enforced, source-grounded)
**Compression**: TOON encoding for token efficiency
**Original**: {len(messages)} messages
**Quality**: Lossless - all meaningful information preserved with source references
"""

    logger.info(f"LangExtract fork summary created: {len(full_summary)} chars")
    return full_summary


def check_langextract_available() -> Dict[str, Any]:
    """Check if LangExtract is available and properly configured."""
    status = {
        "available": LANGEXTRACT_AVAILABLE,
        "api_key_set": bool(os.getenv("GEMINI_API_KEY") or os.getenv("LANGEXTRACT_API_KEY")),
        "version": None
    }

    if LANGEXTRACT_AVAILABLE:
        try:
            status["version"] = lx.__version__ if hasattr(lx, '__version__') else "unknown"
        except Exception:
            status["version"] = "unknown"

    return status
