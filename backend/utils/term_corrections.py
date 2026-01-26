"""
Dynamic term corrections for deprecated API terms.

LLMs have deprecated API terms baked into their training data.
This module provides corrections that are applied to:
1. Agent thoughts/speech (AG-UI stream) - so users see correct terms
2. Conversation history (state) - so agents see correct terms in their context

NOT applied to tool calls - those go through as-is.
"""

import logging

logger = logging.getLogger(__name__)

# Deprecated API terms that agents may hallucinate from training data
# Format: "deprecated_term": "modern_replacement"
DEPRECATED_TERM_REPLACEMENTS = {
    "productVariantUpdate": "productVariantsBulkUpdate",
    # Add more as needed
}


def apply_term_corrections(text: str) -> str:
    """
    Replace deprecated API terms with their modern equivalents.

    Applied to:
    - Agent thoughts and speech (AG-UI stream)
    - Conversation history (so agents see corrected terms)

    NOT applied to:
    - Tool calls (those execute as-is)

    Args:
        text: The text to correct

    Returns:
        Text with deprecated terms replaced
    """
    if not text:
        return text

    for old_term, new_term in DEPRECATED_TERM_REPLACEMENTS.items():
        if old_term in text:
            text = text.replace(old_term, new_term)
            logger.debug(f"[TERM-CORRECTION] Replaced '{old_term}' with '{new_term}'")

    return text
