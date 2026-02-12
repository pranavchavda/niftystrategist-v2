"""LLM-powered autocomplete service for notes using Pydantic AI and Grok-4 Fast"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class AutocompleteRequest(BaseModel):
    """Request for autocomplete suggestions"""

    current_text: str
    note_title: str = ""
    note_category: str = "personal"
    max_tokens: int = 50
    mode: str = "notes"  # "notes", "docs", or "chat"
    context: str = ""  # Recent conversation history for chat mode


class AutocompleteResponse(BaseModel):
    """Response with autocomplete suggestions"""

    suggestion: str
    confidence: float


class AutocompleteService:
    """Service for generating autocomplete suggestions using LLMs"""

    def __init__(self):
        """Initialize the autocomplete agent with Grok-4 Fast via OpenRouter"""
        # Get API key from environment
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            load_dotenv()
            api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            logger.error("OPENROUTER_API_KEY not found in environment or .env file!")
            raise ValueError("OPENROUTER_API_KEY is required for autocomplete service")

        self.api_key = api_key
        logger.info(f"Using OpenRouter with key: {api_key[:8]}...")

        # Set up OpenRouter provider
        provider = OpenAIProvider(
            base_url="https://openrouter.ai/api/v1", api_key=api_key
        )

        # Model name - using gpt-oss-20b
        # model_name = "inception/mercury"
        model_name = "meta-llama/llama-4-scout"
        logger.info(f"Using model: {model_name} via OpenRouter")

        # Create model settings
        model_settings = ModelSettings(temperature=0.7, max_tokens=100)

        # Create the OpenAI chat model with OpenRouter provider
        self.model = OpenAIChatModel(
            model_name, provider=provider, settings=model_settings
        )

        # Create the agent - instructions will be set dynamically based on mode
        self.agent = Agent(
            model=self.model,
            instructions="",  # Will be set in get_suggestion based on mode
        )

    def _get_instructions_for_mode(self, mode: str) -> str:
        """Get system instructions based on autocomplete mode"""

        base_guidelines = """You are a part of the EspressoBot AI system - a suite of intelligent tools created by and for
Pranav Chavda to help with his work at iDrinkCoffee.com.

CRITICAL RULES:
1. Depending on the mode, suggest only the next few words to allow the user to continue typing. Similar to tab completion on a command line interface.
2. Return ONLY the suggestion text that comes IMMEDIATELY AFTER the user's last character
3. DO NOT repeat any text the user has already typed
4. Keep suggestions concise and relevant to the context
5. Never suggest multiple options - provide ONE best suggestion
6. Return ONLY the suggestion text, nothing else (no quotes, no explanations)
7. Match the user's writing style and tone
8. Be context-aware and adapt suggestions based on the text content
9. Prioritize clarity and usefulness over creativity
10. Ensure that your response format is easy to understand and implement

MANDATORY GUIDELINES:
    - If the user types /instruction followed by some test, it is an instruction for you to generate larger blocks of text.
"""

        if mode == "notes":
            return (
                base_guidelines
                + """
MODE: Note-taking autocomplete

Guidelines for notes:
- Use markdown formatting when appropriate
- Suggest emojis when they enhance the meaning naturally
- Keep suggestions conversational and human-like
- Avoid overly formal or robotic language
- For technical notes, suggest relevant terminology
- For personal notes, suggest natural conversational continuations
- Your completions here can be anything from short to long, depending on the context.

Examples:
- If text ends with "The project is", suggest " progressing well"
- If text ends with "TODO:", suggest " Review the design"
- If text ends with "Note:", suggest " This is important"
- If text ends with "Espress", suggest "o Machine"
- If text ends with "Espresso", suggest " machine"
- If text is empty or just whitespace, suggest a relevant starter phrase
- if the is incomplete code typed, suggest the remaining code snippet - ensure that the code is syntactically correct and follows best practices.
"""
            )

        elif mode == "docs":
            return (
                base_guidelines
                + """
MODE: Documentation editor autocomplete

Guidelines for documentation:
- Respect markdown formatting (headers, lists, code blocks)
- Suggest technical and precise continuations
- Focus on clarity and structure
- Use proper technical terminology
- Maintain consistent documentation style

Examples:
- If text ends with "## Installation", suggest " Guide"
- If text ends with "To install, run", suggest " the following command:"
- If text ends with "### Key Features", suggest a newline and bullet point
- If text ends with "```", suggest the language identifier
"""
            )

        elif mode == "chat":
            return (
                base_guidelines
                + """
MODE: Chat message autocomplete

Guidelines for chat:
- Keep suggestions casual and conversational
- Focus on completing common e-commerce/Shopify queries
- Suggest natural conversational flow
- Be helpful and task-oriented
- Consider iDrinkCoffee.com context (coffee, espresso machines, e-commerce)

Examples:
- If text ends with "Can you help me find", suggest " products from Breville?"
- If text ends with "Create a new product for", suggest " the Breville Bambino Plus"
- If text ends with "Show me", suggest " today's sales analytics"
- If text ends with "What are", suggest " the best selling items?"
"""
            )

        else:
            return base_guidelines

    async def get_suggestion(
        self, request: AutocompleteRequest
    ) -> AutocompleteResponse:
        """
        Generate an autocomplete suggestion for the given text.

        Args:
            request: AutocompleteRequest containing current text and context

        Returns:
            AutocompleteResponse with suggestion and confidence score
        """
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set. Cannot generate suggestions.")
            return AutocompleteResponse(suggestion="", confidence=0.0)

        try:
            # Get mode-specific instructions
            instructions = self._get_instructions_for_mode(request.mode)

            # Build context for the agent based on mode
            if request.mode == "notes":
                context = f"""
Note Title: {request.note_title or "Untitled"}
Category: {request.note_category}
Current Text: {request.current_text}

Generate a natural continuation for this text. Return ONLY the suggestion (1-5 words), nothing else. Keep it concise and relevant to the context.
"""
            elif request.mode == "docs":
                context = f"""
Current Documentation Text: {request.current_text}

Generate a natural continuation for this documentation. Return ONLY the suggestion, nothing else. Respect markdown formatting.
"""
            elif request.mode == "chat":
                # Include conversation context if provided
                context_prefix = ""
                if request.context:
                    context_prefix = f"""
Recent Conversation:
{request.context}

---

"""
                context = f"""{context_prefix}Current Message: {request.current_text}

Complete this chat message. Return ONLY the completion text that should come immediately after what the user typed. DO NOT include a response from the assistant. Only complete the user's message.
"""
            else:
                context = f"Current Text: {request.current_text}\n\nGenerate a natural continuation."

            # Create a new agent instance with mode-specific instructions
            # This ensures each mode gets the appropriate system prompt
            mode_agent = Agent(
                model=self.model, instructions=instructions, retries=3, output_retries=3
            )

            # Call the agent
            result = await mode_agent.run(context)

            # Extract suggestion from result.output
            full_suggestion = str(result.output).strip() if result.output else ""

            # Clean up the suggestion - remove any extra formatting
            full_suggestion = (
                full_suggestion.replace("*", "")
                .replace("`", "")
                .replace('"', "")
                .strip()
            )

            # Extract only the delta (the part that's not already in current_text)
            # This makes it seamless like Windsurf/Cursor autocomplete
            suggestion = self._extract_delta(request.current_text, full_suggestion)

            # Calculate confidence based on suggestion length and content
            confidence = self._calculate_confidence(suggestion, request.current_text)

            logger.debug(
                f"Full suggestion: '{full_suggestion}' -> Delta: '{suggestion}' with confidence {confidence}"
            )

            return AutocompleteResponse(suggestion=suggestion, confidence=confidence)

        except Exception as e:
            logger.error(f"Error generating autocomplete suggestion: {e}")
            logger.debug(f"Exception details: {type(e).__name__}")
            return AutocompleteResponse(suggestion="", confidence=0.0)

    def _extract_delta(self, current_text: str, full_suggestion: str) -> str:
        """
        Extract only the new part (delta) from the full suggestion.

        For example:
        - current_text: "Espress"
        - full_suggestion: "Espresso Machine"
        - returns: "o Machine"

        Args:
            current_text: The text the user has already typed
            full_suggestion: The full suggestion from the LLM

        Returns:
            Only the part that needs to be added (the delta)
        """
        if not full_suggestion or not current_text:
            return full_suggestion

        # Find the longest common prefix between current_text and full_suggestion
        # This handles cases where the suggestion starts with what the user typed
        common_length = 0
        for i in range(min(len(current_text), len(full_suggestion))):
            if current_text[i].lower() == full_suggestion[i].lower():
                common_length = i + 1
            else:
                break

        # Return only the part after the common prefix
        delta = full_suggestion[common_length:].lstrip()

        return delta if delta else full_suggestion

    def _calculate_confidence(self, suggestion: str, context: str) -> float:
        """
        Calculate confidence score for the suggestion.

        Args:
            suggestion: The generated suggestion
            context: The current text context

        Returns:
            Confidence score between 0 and 1
        """
        if not suggestion:
            return 0.0

        # Base confidence on suggestion length (prefer 1-5 words)
        word_count = len(suggestion.split())
        if 1 <= word_count <= 5:
            confidence = 0.9
        elif word_count > 5:
            confidence = 0.7
        else:
            confidence = 0.5

        # Boost confidence if suggestion ends with punctuation
        if suggestion[-1] in ".!?,;:":
            confidence = min(1.0, confidence + 0.1)

        return min(1.0, confidence)


# Global instance
_autocomplete_service: Optional[AutocompleteService] = None


def get_autocomplete_service() -> AutocompleteService:
    """Get or create the global autocomplete service instance"""
    global _autocomplete_service
    if _autocomplete_service is None:
        _autocomplete_service = AutocompleteService()
    return _autocomplete_service
