"""
Function Call Validator - Detects and recovers from malformed function calls

Some models (especially experimental/smaller ones) hallucinate XML-style tool calls
or other incorrect formats instead of following Pydantic AI's structured format.

This module:
1. Detects malformed function call patterns
2. Provides retry logic with explicit format instructions
3. Falls back to reliable models if needed
"""

import logging
import re
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class FunctionCallError(Enum):
    """Types of function call errors"""
    XML_STYLE = "xml_style"  # Model used <function_call> or <tool> XML tags
    JSON_IN_TEXT = "json_in_text"  # Model put JSON in markdown code blocks
    NARRATIVE = "narrative"  # Model narrated instead of calling ("I will call...")
    UNKNOWN_FORMAT = "unknown_format"  # Other malformed formats
    LOOP_DETECTED = "loop_detected"  # Model stuck repeating same pattern


class FunctionCallValidator:
    """
    Validates model outputs for proper function calling format.

    Detects common issues where models hallucinate incorrect formats:
    - XML-style tags: <function_call>, <tool_call>, etc.
    - JSON in code blocks: ```json\n{"tool": "..."}```
    - Narrative instead of calls: "I will now call the search tool..."
    - Loops: Repeating the same malformed pattern
    """

    # Patterns that indicate malformed function calls
    XML_PATTERNS = [
        # Standard XML/Tag patterns
        r'<function_call[^>]*>',
        r'<tool_call[^>]*>',
        r'<tool[^>]*>',
        r'<invoke[^>]*>',
        r'<action[^>]*>',
        r'<parameter[^>]*>',
        
        # Minimax specific patterns (often missing opening < or using minimax: namespace)
        r'minimax:tool_call',
        r'<minimax:tool_call',
        
        # Anthropic/Claude specific patterns
        r'antml:invoke',
        r'antml:parameter',
        r'antml:function',
        
        # Common end tags that might appear isolated
        r'</function_call>',
        r'</tool_call>',
        r'</invoke>',
    ]

    NARRATIVE_PATTERNS = [
        r'(?i)\b(I will|I am going to|I need to|now I will|let me|I\'ll)\s+(call|invoke|execute|run|use|search|find|check|retrieve|list)\s+(the\s+)?(\w+)\s+(tool|function|agent|notes|data|products|orders|emails|items)?',
        r'(?i)calling\s+the\s+\w+\s+tool',
        r'(?i)invoking\s+the\s+\w+\s+function',
    ]

    JSON_BLOCK_PATTERNS = [
        r'```json\s*\n\s*\{[^`]*"tool"[^`]*\}',
        r'```\s*\n\s*\{[^`]*"function"[^`]*\}',
    ]

    def __init__(self):
        """Initialize validator"""
        self.error_history: List[FunctionCallError] = []
        self.max_loop_threshold = 3  # After 3 identical errors, it's a loop

    def detect_malformed_call(self, text: str) -> Optional[FunctionCallError]:
        """
        Detect if the model output contains malformed function calls.

        Args:
            text: Model output text to check

        Returns:
            FunctionCallError type if malformed, None if valid
        """
        # Strip code blocks to avoid false positives (e.g. documentation or examples)
        text_to_check = re.sub(r'```[\s\S]*?```', '', text)  # Fenced code blocks
        text_to_check = re.sub(r'`[^`]+`', '', text_to_check)  # Inline code

        # Check for XML-style function calls
        for pattern in self.XML_PATTERNS:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                logger.warning(f"Detected XML-style function call pattern: {pattern}")
                return FunctionCallError.XML_STYLE

        # Check for narrative instead of actual calls
        for pattern in self.NARRATIVE_PATTERNS:
            if re.search(pattern, text_to_check):
                logger.warning(f"Detected narrative instead of function call: {pattern}")
                return FunctionCallError.NARRATIVE

        # Check for JSON in code blocks
        # Note: We check the ORIGINAL text for this one, since stripping code blocks would hide it!
        for pattern in self.JSON_BLOCK_PATTERNS:
            if re.search(pattern, text):
                logger.warning(f"Detected JSON function call in code block: {pattern}")
                return FunctionCallError.JSON_IN_TEXT

        return None

    def record_error(self, error: FunctionCallError) -> bool:
        """
        Record an error and check if we're in a loop.

        Args:
            error: The error type that occurred

        Returns:
            True if loop detected (same error 3+ times), False otherwise
        """
        self.error_history.append(error)

        # Check last N errors
        recent_errors = self.error_history[-self.max_loop_threshold:]

        if len(recent_errors) >= self.max_loop_threshold:
            # If all recent errors are the same, it's a loop
            if all(e == error for e in recent_errors):
                logger.error(f"Loop detected: {error.value} error repeated {self.max_loop_threshold} times")
                return True

        return False

    def get_recovery_instructions(self, error: FunctionCallError, text: Optional[str] = None) -> str:
        """
        Get recovery instructions to send to the model.

        Args:
            error: The error type that occurred
            text: The malformed text (used to extract intended tool name)

        Returns:
            Clear instructions for the model on proper format
        """
        # Try to extract the intended tool name for more specific guidance
        tool_name = "YOUR_INTENDED_TOOL"
        args_hint = "relevant_arguments"
        
        if text:
            # Try parsing XML/Minimax
            xml_match = re.search(r'(?:invoke|tool|function|call)[^>]*name=["\']([^"\']+)["\']', text, re.IGNORECASE)
            if xml_match:
                tool_name = xml_match.group(1)
                
            # Try parsing JSON-like
            if tool_name == "YOUR_INTENDED_TOOL":
                json_match = re.search(r'["\'](?:tool|function)["\']\s*:\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
                if json_match:
                    tool_name = json_match.group(1)
            
            # Try parsing narrative
            if tool_name == "YOUR_INTENDED_TOOL":
                # First try verb + noun pattern
                narrative_match = re.search(r'(?:call|use|run|search|find|list)\s+(?:the\s+)?([a-zA-Z0-9_]+)', text, re.IGNORECASE)
                if narrative_match and narrative_match.group(1).lower() not in ['tool', 'function', 'agent']:
                    tool_name = narrative_match.group(1)
                
                # Fallback: Look for snake_case words which are likely tool names
                if tool_name == "YOUR_INTENDED_TOOL":
                    snake_match = re.search(r'\b([a-z]+_[a-z0-9_]+)\b', text)
                    if snake_match:
                        tool_name = snake_match.group(1)

        common_header = """Validation feedback (tool invocation failure)
❌ ERROR: You put the tool call in the wrong place.

You sent the tool call as text inside the `content` field.
Use the separate `tool_calls` field instead.

WRONG (What you did):
{
  "content": "minimax:tool_call <invoke name='search'>...</invoke>",
  "tool_calls": null
}

CORRECT (What you must do):
{
  "content": null,
  "tool_calls": [
    {
      "function": {
        "name": "YOUR_TOOL_NAME",
        "arguments": "..."
      }
    }
  ]
}
"""

        if error == FunctionCallError.XML_STYLE or error == FunctionCallError.JSON_IN_TEXT:
            return f"""{common_header}
✅ REQUIRED FIX:
Stop generating text. Emit a **native tool call event** for:
Tool: `{tool_name}`
Args: <{args_hint}>

🔁 IMPORTANT:
- Do NOT flatten the tool call into your text response.
- **Immediately emit the tool-call event now.**"""

        elif error == FunctionCallError.NARRATIVE:
            return f"""{common_header}
✅ REQUIRED FIX:
You narrated an action ("{tool_name}") but didn't execute it.
Stop generating text. Emit a **native tool call event** for:
Tool: `{tool_name}`

🔁 IMPORTANT:
- Do not just say you will do it.
- **Immediately emit the tool-call event now.**"""

        else:
            return f"""{common_header}
✅ REQUIRED FIX:
Your next assistant response must be an **actual native tool-call event**.

🔁 IMPORTANT:
- Do not explain. Do not apologize.
- **Immediately emit the tool-call event now.**"""

    def should_fallback_model(self, model_id: str) -> Optional[str]:
        """
        Determine if we should fall back to a more reliable model.

        Args:
            model_id: Current model being used

        Returns:
            Recommended fallback model ID, or None if no fallback needed
        """
        # If we've detected a loop, fall back to a known-good model
        if len(self.error_history) >= self.max_loop_threshold:
            logger.warning(f"Too many function call errors with {model_id}, recommending fallback")

            # Fallback hierarchy: Claude Haiku 4.5 > GPT-4.1 > GPT-4.1-mini
            if "claude" not in model_id.lower():
                return "claude-haiku-4-5-20251001"  # Claude Haiku 4.5 (most reliable)
            elif "gpt-4.1" not in model_id.lower():
                return "gpt-4.1"  # GPT-4.1 (very reliable)
            else:
                return "gpt-4.1-mini"  # Last resort

        return None

    def reset(self):
        """Reset error history (call this when switching models or conversations)"""
        self.error_history.clear()
        logger.debug("Function call validator reset")


# Global singleton
_validator_instance = None

def get_function_call_validator() -> FunctionCallValidator:
    """Get singleton validator instance"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = FunctionCallValidator()
    return _validator_instance


# Model reliability scores (0.0-1.0) based on function calling capability
MODEL_RELIABILITY = {
    # Tier 1: Excellent function calling (0.95+)
    "claude-haiku-4-5-20251001": 0.98,
    "claude-sonnet-4-5-20241022": 0.99,
    "gpt-4.1": 0.97,
    "gpt-5": 0.98,

    # Tier 2: Good function calling (0.85-0.94)
    "gpt-4.1-mini": 0.90,
    "gpt-5-mini": 0.92,
    "openai/gpt-oss-120b": 0.88,

    # Tier 3: Acceptable with monitoring (0.70-0.84)
    "z-ai/glm-4.6": 0.82,
    "deepseek/deepseek-v3.1-terminus": 0.80,
    "x-ai/grok-4-fast": 0.85,

    # Tier 4: Experimental - high failure rate (0.50-0.69)
    "moonshot/kimi-k2": 0.65,  # Known issues with function calling
    "anthropic/claude-3-opus": 0.75,  # Older model, less reliable

    # Unknown models default to 0.70 (acceptable but monitor closely)
}

def get_model_reliability(model_id: str) -> float:
    """
    Get reliability score for a model's function calling capability.

    Args:
        model_id: Model identifier

    Returns:
        Reliability score 0.0-1.0 (higher is better)
    """
    # Check exact match
    if model_id in MODEL_RELIABILITY:
        return MODEL_RELIABILITY[model_id]

    # Check partial matches (e.g., "claude-haiku" in "anthropic:claude-haiku-...")
    for known_model, score in MODEL_RELIABILITY.items():
        if known_model in model_id:
            return score

    # Unknown model - assume acceptable but monitor
    logger.info(f"Unknown model reliability for {model_id}, defaulting to 0.70")
    return 0.70
