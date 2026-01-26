"""
Vision Agent - Handles image analysis, OCR, visual Q&A, and multimodal tasks

Uses vision-capable models for:
- Image analysis and description
- OCR (text extraction from images)
- Visual question answering
- Product image analysis
- Document parsing
- Screenshot analysis
"""

from pydantic import BaseModel
from pydantic_ai import RunContext
from pydantic_ai.messages import BinaryContent
from typing import Optional
import logging
from pathlib import Path
import mimetypes

# Import base agent for proper setup
from agents.base_agent import IntelligentBaseAgent, AgentConfig

logger = logging.getLogger(__name__)

# Logfire for observability
try:
    from config import get_logfire
    logfire = get_logfire()
except Exception:
    logfire = None


class VisionDeps(BaseModel):
    """Dependencies for vision agent"""
    user_email: Optional[str] = None
    conversation_id: Optional[str] = None


class VisionAgent(IntelligentBaseAgent[VisionDeps, str]):
    """
    Vision Agent for multimodal image analysis tasks

    Capabilities:
    - Analyze product images for quality, compliance, descriptions
    - Extract text from images (OCR)
    - Answer questions about uploaded images
    - Analyze screenshots and documents
    - Generate product descriptions from images
    """

    def __init__(self):
        # Configure the vision agent
        config = AgentConfig(
            name="vision",
            description="Vision analysis specialist for e-commerce",
            model_name="x-ai/grok-4.1-fast",
            use_openrouter=True,
            temperature=0.7
        )

        # Initialize with base agent
        super().__init__(
            config=config,
            deps_type=VisionDeps,
            output_type=str
        )

        logger.info("[VisionAgent] Initialized with x-ai/grok-4.1-fast")

    def _get_system_prompt(self) -> str:
        """System prompt for vision agent"""
        return """You are a vision analysis specialist for an e-commerce platform.

Your capabilities:
- Analyze product images for quality, accuracy, and compliance
- Extract text from images (OCR) with high accuracy
- Answer detailed questions about visual content
- Generate compelling product descriptions from images
- Identify brands, models, and specifications from product photos
- Analyze screenshots and documents

Guidelines:
1. Be thorough and accurate in your visual analysis
2. For product images: mention brand, model, condition, key features
3. For OCR tasks: extract ALL visible text accurately
4. For questions: provide detailed, specific answers based on what you see
5. Note any quality issues, missing information, or concerns
6. Use professional e-commerce terminology

Always base your response ONLY on what you can actually see in the image.
If you're unsure, say so rather than guessing."""

    def _register_tools(self) -> None:
        """Register vision-specific tools"""
        # Vision agent uses direct method calls instead of registered tools
        # since it needs access to image files
        pass

    @staticmethod
    def encode_image(image_path: str) -> str:
        """Encode image to base64 for API"""
        import base64
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def analyze_image(
        self,
        image_path: str,
        query: str,
        user_email: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        Analyze an image and answer a query about it

        Args:
            image_path: Path to the image file
            query: Question or instruction about the image
            user_email: User's email for context
            conversation_id: Conversation ID for tracking

        Returns:
            Analysis result as text
        """
        import time

        # Create Logfire span for vision analysis
        if logfire:
            span = logfire.span(
                "vision.analyze_image",
                image_path=image_path,
                query_preview=query[:100]
            )
        else:
            from contextlib import nullcontext
            span = nullcontext()

        try:
            async with span:
                start_time = time.time()

                logger.info(f"[VisionAgent] Analyzing image: {image_path} with query: {query[:50]}...")
                if logfire:
                    logfire.info("vision.started", image_path=image_path, query=query[:200])

                # Check if file exists
                if not Path(image_path).exists():
                    if logfire:
                        logfire.error("vision.file_not_found", path=image_path)
                    return f"Error: Image file not found at {image_path}"

                # Read the image file as binary
                image_path_obj = Path(image_path)
                try:
                    with open(image_path_obj, 'rb') as f:
                        image_data = f.read()
                except Exception as e:
                    if logfire:
                        logfire.error("vision.read_error", path=image_path, error=str(e))
                    return f"Error reading image file: {str(e)}"

                # Detect media type from file extension
                media_type, _ = mimetypes.guess_type(str(image_path_obj))
                if not media_type or not media_type.startswith('image/'):
                    # Default to jpeg if can't detect
                    media_type = 'image/jpeg'
                    logger.warning(f"Could not detect image type for {image_path}, using {media_type}")

                # Build multimodal prompt with binary image content
                # Per Pydantic AI docs, user_prompt can be a list of str and BinaryContent objects
                user_prompt = [
                    BinaryContent(image_data, media_type=media_type),  # The image as binary
                    query  # The question about the image
                ]

                deps = VisionDeps(
                    user_email=user_email,
                    conversation_id=conversation_id
                )

                # Pass multimodal prompt (image + text)
                logger.info(f"[VisionAgent] Sending {len(image_data)} bytes of {media_type} with query")
                result = await self.agent.run(user_prompt, deps=deps)

                # Extract output from result
                if hasattr(result, 'output'):
                    output = result.output
                else:
                    output = str(result)

                # Log completion
                total_time = time.time() - start_time
                logger.info(f"[VisionAgent] Analysis complete: {len(output)} chars")
                if logfire:
                    logfire.info(
                        "vision.completed",
                        time_ms=int(total_time * 1000),
                        image_size_bytes=len(image_data),
                        output_length=len(output),
                        media_type=media_type
                    )

                return output

        except Exception as e:
            logger.error(f"[VisionAgent] Error: {e}", exc_info=True)
            if logfire:
                logfire.error("vision.error", image_path=image_path, error=str(e), error_type=type(e).__name__)
            return f"Error analyzing image: {str(e)}"

    async def extract_text(
        self,
        image_path: str,
        user_email: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        Extract all text from an image (OCR)

        Args:
            image_path: Path to the image file
            user_email: User's email for context
            conversation_id: Conversation ID for tracking

        Returns:
            Extracted text
        """
        logger.info(f"[VisionAgent] Extracting text from: {image_path}")

        query = """Extract ALL visible text from this image.
Format the output clearly, preserving the structure and layout where possible.
If there's no text, say 'No text found in image'."""

        return await self.analyze_image(
            image_path=image_path,
            query=query,
            user_email=user_email,
            conversation_id=conversation_id
        )

    async def analyze_product_image(
        self,
        image_path: str,
        user_email: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        Analyze a product image and generate a detailed description

        Args:
            image_path: Path to the product image
            user_email: User's email for context
            conversation_id: Conversation ID for tracking

        Returns:
            Product analysis and description
        """
        logger.info(f"[VisionAgent] Analyzing product image: {image_path}")

        query = """Analyze this product image in detail.

Provide:
1. Product identification (brand, model, type)
2. Visual condition and quality
3. Key features visible in the image
4. Notable details (colors, materials, design elements)
5. Any text or labels visible
6. Suggested product title and description
7. Any quality concerns or missing information

Format your response clearly with sections."""

        return await self.analyze_image(
            image_path=image_path,
            query=query,
            user_email=user_email,
            conversation_id=conversation_id
        )


# Singleton instance
vision_agent = VisionAgent()
