"""
FastAPI Main Application for Nifty Strategist v2 - AI Trading Agent
"""

import os
import json
import logging
import asyncio
import re
import mimetypes
from typing import Optional, Dict, Any, List, Union
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from utils.datetime_utils import utc_now_naive
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv

# Import our agents and models
from agents.orchestrator import OrchestratorAgent, OrchestratorDeps
from agents.web_search_agent import WebSearchAgent, WebSearchDeps
from agents.vision_agent import vision_agent
from models.state import ConversationState, MessageRole
from pydantic_ai.messages import BinaryContent
from config.models import is_vision_capable
from auth import (
    User, TokenData,
    create_access_token, get_current_user, get_current_user_optional,
    requires_permission, GoogleOAuthMock
)
# Database imports
from database import DatabaseManager, Conversation, Message, MemoryOps
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# API routers
from api import dashboard, stats


# Helper to process messages with vision capability detection
async def process_message_with_vision(
    message_content: str,
    model_id: str,
) -> Union[str, List[Union[str, BinaryContent]]]:
    """
    Process user message and convert image attachments to BinaryContent if model supports vision.

    This enables vision-capable models (Claude Haiku 4.5, Sonnet 4.5, GPT-5) to analyze images
    directly, while non-vision models continue using VisionAgent delegation.

    Args:
        message_content: User's message content (may include image file path reference)
        model_id: Orchestrator model ID (e.g., "claude-haiku-4.5")

    Returns:
        - str: Original message (if no image or non-vision model)
        - List[BinaryContent, str]: Multimodal input (if vision-capable model with image)
    """
    # Pattern to detect uploaded image references from frontend
    # Format: "[Uploaded image: filename.jpg]\nFile path: backend/uploads/user_at_example_com/..."
    image_pattern = r'\[Uploaded (?:image|file): [^\]]+\]\s*\nFile path: (.+?)(?:\n|$)'
    match = re.search(image_pattern, message_content, re.IGNORECASE)

    if not match:
        # No image attachment - return as-is
        return message_content

    # Extract image path
    image_path = match.group(1).strip()
    logger.info(f"[Vision] Detected image attachment: {image_path}")

    # Check if model supports vision
    if not is_vision_capable(model_id):
        # Non-vision model - keep text format so orchestrator can delegate to VisionAgent
        logger.info(f"[Vision] Model {model_id} doesn't support vision - keeping text format for VisionAgent delegation")
        return message_content

    # Vision-capable model - convert to multimodal format
    logger.info(f"[Vision] Model {model_id} supports vision - converting image to BinaryContent")

    # Remove the file path reference from text (keep user's actual message)
    text_without_path = re.sub(image_pattern, '', message_content, flags=re.IGNORECASE).strip()

    # Read image file
    try:
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            logger.error(f"[Vision] Image file not found: {image_path}")
            return f"{text_without_path}\n\n[Error: Image file not found at {image_path}]"

        with open(image_path_obj, 'rb') as f:
            image_data = f.read()

        # Detect media type
        media_type, _ = mimetypes.guess_type(str(image_path_obj))
        if not media_type or not media_type.startswith('image/'):
            media_type = 'image/jpeg'  # Default fallback
            logger.warning(f"[Vision] Could not detect image type for {image_path}, using {media_type}")

        logger.info(f"[Vision] Image available at {image_path}")

        # For graphics_designer and other image agents: pass path, not BinaryContent
        # This allows multiple images and simpler handling
        # Format: Add image reference that orchestrator can extract
        image_ref = f"\n\n[Image uploaded: {image_path}]"
        return text_without_path + image_ref if text_without_path else f"Analyze this image.{image_ref}"

    except Exception as e:
        logger.error(f"[Vision] Error reading image file: {e}", exc_info=True)
        return f"{text_without_path}\n\n[Error reading image: {str(e)}]"


# Helper to retrieve user memories
async def get_user_memories_for_context(
    user_email: str,
    current_message: Optional[str] = None,
    limit: int = 10,
    similarity_threshold: float = 0.35
) -> List[str]:
    """
    Retrieve user's most relevant memories for conversation context using semantic search.

    Args:
        user_email: User's email (used as user_id)
        current_message: Current user message to find relevant memories for
        limit: Maximum number of memories to return
        similarity_threshold: Minimum similarity score (0.0-1.0) for memory inclusion

    Returns list of memory facts as strings for injection into system prompt.
    """
    try:
        async with db_manager.async_session() as db:
            # If we have a current message, use semantic search
            if current_message and current_message.strip():
                # Get embedding for current message
                import openai
                openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

                try:
                    embedding_response = await openai_client.embeddings.create(
                        model="text-embedding-3-large",
                        input=current_message
                    )
                    query_embedding = embedding_response.data[0].embedding

                    # Search for semantically similar memories
                    memories_with_scores = await MemoryOps.search_memories_semantic(
                        db,
                        user_id=user_email,
                        embedding=query_embedding,
                        limit=limit,
                        similarity_threshold=similarity_threshold
                    )

                    # Log similarity scores for debugging
                    if memories_with_scores:
                        logger.info(f"[Memory] Found {len(memories_with_scores)} relevant memories (threshold: {similarity_threshold})")
                        for mem, score in memories_with_scores[:3]:  # Log top 3
                            logger.info(f"[Memory] {score:.3f}: {mem.fact[:60]}...")

                    # Log to Logfire for observability
                    log_memory_retrieval(
                        user_id=user_email,
                        query=current_message,
                        memories_found=len(memories_with_scores),
                        method="semantic_search"
                    )

                    # Return just the fact text
                    return [mem.fact for mem, score in memories_with_scores]

                except Exception as e:
                    logger.error(f"Semantic search failed, falling back to recent memories: {e}")
                    # Fallback to recent memories if embedding fails
                    pass

            # Fallback: Get recent memories (no semantic search)
            memories = await MemoryOps.get_user_memories(
                db,
                user_id=user_email,
                limit=limit
            )

            logger.info(f"[Memory] Using {len(memories)} recent memories (no semantic search)")

            # Log to Logfire for observability
            log_memory_retrieval(
                user_id=user_email,
                query=current_message,
                memories_found=len(memories),
                method="recent"
            )

            return [mem.fact for mem in memories]

    except Exception as e:
        logger.error(f"Failed to retrieve memories for {user_email}: {e}")
        return []

# Helper to save conversations to database
async def save_conversation_to_db(thread_id: str, user_email: str, message_content: str):
    """Save conversation to database"""
    try:
        async with db_manager.async_session() as db:
            # Check if conversation exists
            query = select(Conversation).where(Conversation.id == thread_id)
            result = await db.execute(query)
            conv = result.scalar_one_or_none()

            if not conv:
                # Extract title from first message
                title = message_content[:50] + "..." if len(message_content) > 50 else message_content

                # Create new conversation
                conv = Conversation(
                    id=thread_id,
                    user_id=user_email,
                    title=title,
                    created_at=utc_now_naive(),
                    updated_at=utc_now_naive()
                )
                db.add(conv)
            else:
                # Update existing conversation
                conv.updated_at = utc_now_naive()

            # Create message
            import uuid
            message_id = f"msg_{uuid.uuid4().hex[:12]}"

            msg = Message(
                conversation_id=thread_id,
                message_id=message_id,
                role="user",
                content=message_content,
                timestamp=utc_now_naive()
            )
            db.add(msg)

            await db.commit()
            logger.info(f"Saved conversation {thread_id} to database")
    except Exception as e:
        logger.error(f"Failed to save conversation to database: {e}")
        # Don't fail the request if database save fails


async def save_assistant_message_to_db(
    thread_id: str,
    message_content: str,
    message_id: Optional[str] = None,
    tool_calls: Optional[list] = None,
    reasoning: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None
):
    """Save assistant response to database with tool calls, reasoning, and token counts"""
    logger.info(f"[SAVE DEBUG] save_assistant_message_to_db called with: thread={thread_id}, msg_len={len(message_content)}, tool_calls={len(tool_calls) if tool_calls else 0}, reasoning={len(reasoning) if reasoning else 0}, tokens=({input_tokens}, {output_tokens})")
    try:
        async with db_manager.async_session() as db:
            # Ensure conversation exists
            query = select(Conversation).where(Conversation.id == thread_id)
            result = await db.execute(query)
            conv = result.scalar_one_or_none()

            if not conv:
                logger.warning(f"Conversation {thread_id} not found when saving assistant message")
                return

            # Update conversation timestamp
            conv.updated_at = utc_now_naive()

            # Generate message ID if not provided
            import uuid
            if not message_id:
                message_id = f"msg_{uuid.uuid4().hex[:12]}"

            # Save the assistant message with tool calls, reasoning, and token counts
            msg = Message(
                conversation_id=thread_id,
                message_id=message_id,
                role="assistant",
                content=message_content,
                timestamp=utc_now_naive(),
                tool_calls=tool_calls or [],  # Save tool calls as JSON
                reasoning=reasoning,  # Save reasoning as TEXT
                input_tokens=input_tokens,  # Estimated input tokens
                output_tokens=output_tokens  # Estimated output tokens
            )
            db.add(msg)
            await db.commit()

            # Log what was saved
            log_parts = [f"Saved assistant message {message_id}"]
            if tool_calls:
                log_parts.append(f"{len(tool_calls)} tool calls")
            if reasoning:
                log_parts.append(f"reasoning ({len(reasoning)} chars)")
            if input_tokens or output_tokens:
                log_parts.append(f"tokens ({input_tokens}/{output_tokens})")
            logger.info(f"{' with '.join(log_parts)} to conversation {thread_id}")

            # Log agent response to Logfire for observability
            log_agent_response(
                thread_id=thread_id,
                user_id=conv.user_id,  # Get user_id from conversation record
                response=message_content,
                model=None,  # Model info not available here
                tokens_used=(input_tokens or 0) + (output_tokens or 0),
                metadata={
                    'message_id': message_id,
                    'tool_calls': len(tool_calls) if tool_calls else 0,
                    'has_reasoning': bool(reasoning),
                    'has_error': False,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens
                }
            )

    except Exception as e:
        logger.error(f"Failed to save assistant message to database: {e}")
        # Don't fail the request if DB save fails


# Load environment variables
load_dotenv()

# Configure logging FIRST (before Logfire)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add filter to suppress harmless connection pool warnings during shutdown/reload
class PoolTerminationFilter(logging.Filter):
    """Filter to suppress expected warnings during database connection lifecycle"""
    def filter(self, record):
        # Suppress harmless connection pool warnings
        # These occur during shutdown/reload and don't indicate a problem when using proper context managers
        if record.name == "sqlalchemy.pool.impl.AsyncAdaptedQueuePool":
            message = record.getMessage()

            # Suppress garbage collector cleanup warnings (connections properly use async context managers)
            if "garbage collector is trying to clean up" in message:
                return False

            # Suppress "Exception terminating connection" errors with CancelledError
            # CancelledError can be in the message OR in the exception traceback
            if "Exception terminating connection" in message:
                # Check if CancelledError is in the message
                if "CancelledError" in message:
                    return False
                # Check if exception info contains CancelledError
                if record.exc_info:
                    exc_type, exc_value, exc_tb = record.exc_info
                    if exc_type and "CancelledError" in exc_type.__name__:
                        return False
                    # Also check the formatted exception string
                    import traceback
                    if exc_type:
                        exc_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
                        if "CancelledError" in exc_str:
                            return False

        return True  # Allow all other logs

# Apply filter to SQLAlchemy pool logger
pool_logger = logging.getLogger("sqlalchemy.pool.impl.AsyncAdaptedQueuePool")
pool_logger.addFilter(PoolTerminationFilter())

# Suppress SQLAlchemy warnings about garbage collector cleanup (harmless with proper context managers)
import warnings
from sqlalchemy.exc import SAWarning
warnings.filterwarnings(
    "ignore",
    message=".*garbage collector is trying to clean up.*",
    category=SAWarning
)

# Configure Logfire for observability (after logging, before other init)
from config import configure_logfire
from config.logfire_config import (
    log_user_message,
    log_agent_response,
    log_memory_retrieval,
    log_tool_call
)
logfire_enabled = configure_logfire(
    service_name="espressobot",
    environment=os.getenv("ENVIRONMENT", "development"),
    enable_in_dev=True  # Enable even without token for local tracing
)
logger.info(f"Logfire observability: {'enabled' if logfire_enabled else 'disabled'}")

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/espressobot')
db_manager = DatabaseManager(DATABASE_URL)

# Initialize trade persistence service (for paper trading history)
from services.trade_persistence import init_trade_persistence
trade_persistence = init_trade_persistence(db_manager.async_session)
logger.info("Trade persistence service initialized")

# Shared Upstox client for paper trading (loads portfolio from DB)
from services.upstox_client import UpstoxClient
shared_upstox_client = UpstoxClient(paper_trading=True, user_id=1)
logger.info(f"Upstox client initialized (paper_trading={shared_upstox_client.paper_trading})")

# Try to import AG-UI for better streaming support
try:
    from pydantic_ai.ag_ui import handle_ag_ui_request
    from utils import enhanced_handle_ag_ui_request
    from utils.response_capture import ResponseCapture
    HAS_AG_UI = True
    logger.info("AG-UI support enabled for optimized streaming with enhanced events")
except ImportError:
    HAS_AG_UI = False
    logger.info("AG-UI not installed. Using default SSE streaming")


# Request/Response models
class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    model_config = ConfigDict(populate_by_name=True)

    message: str
    conv_id: Optional[str] = Field(None, alias="conv_id")
    user_id: Optional[str] = Field(default="default_user")
    stream: Optional[bool] = False
    image_url: Optional[str] = None
    file_data: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    conversation_id: str
    agent_used: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(BaseModel):
    """Model for conversation messages"""
    id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationData(BaseModel):
    """Model for conversation data"""
    id: str
    user_id: str
    messages: List[ConversationMessage]
    created_at: str
    updated_at: str
    title: Optional[str] = None


# Global agents (initialized on startup)
orchestrator: Optional[OrchestratorAgent] = None  # Default orchestrator
orchestrator_cache: Dict[str, OrchestratorAgent] = {}  # Cache orchestrators by model ID
web_search_agent: Optional[WebSearchAgent] = None
vision_agent_instance: Optional[Any] = None  # Vision agent (imported as function)

# In-memory storage (replace with database in production)
conversation_states: Dict[str, ConversationState] = {}
conversation_messages: Dict[str, List[ConversationMessage]] = {}


async def get_orchestrator_for_model(model_id: str, user_id: Optional[int] = None) -> OrchestratorAgent:
    """
    Get or create an orchestrator for the specified model.

    If user_id is provided and user has MCP servers configured, creates a fresh
    orchestrator with user-specific MCP toolsets (not cached).

    Otherwise, returns cached orchestrator for the model.

    Args:
        model_id: Model ID (e.g., "claude-haiku-4.5")
        user_id: Optional user ID to load user-specific MCP servers

    Returns:
        OrchestratorAgent instance
    """
    from agents.vision_agent import vision_agent as va
    from database.models import AIModel
    from sqlalchemy import select
    global orchestrator_cache, web_search_agent, vision_agent_instance

    # Check model reliability for function calling
    from utils.function_call_validator import get_model_reliability

    reliability = get_model_reliability(model_id)

    if reliability < 0.70:
        logger.warning(
            f"⚠️  Model {model_id} has low function calling reliability ({reliability:.2f}/1.0). "
            f"May experience malformed function calls (XML tags, loops). "
            f"Recommend using Claude Haiku 4.5 (0.98) or GPT-4.1 (0.97) instead."
        )
    elif reliability < 0.85:
        logger.info(
            f"ℹ️  Model {model_id} has acceptable function calling reliability ({reliability:.2f}/1.0). "
            f"Monitoring for potential issues."
        )
    else:
        logger.debug(f"✅ Model {model_id} has excellent function calling reliability ({reliability:.2f}/1.0)")

    # If user_id provided, check if user has MCP servers configured
    user_mcp_servers = []
    if user_id is not None:
        async with db_manager.async_session() as db:
            from services.mcp_manager import MCPManager
            mcp_manager = MCPManager(db)

            # Spawn user MCP servers
            user_mcp_servers = await mcp_manager.spawn_user_mcp_servers(user_id)

            if user_mcp_servers:
                # User has MCP servers - create fresh orchestrator (don't use cache)
                logger.info(f"Creating user-specific orchestrator with {len(user_mcp_servers)} MCP servers for user {user_id}")

                # Fetch model from database
                result = await db.execute(
                    select(AIModel).where(AIModel.model_id == model_id)
                )
                ai_model = result.scalar_one_or_none()

                if not ai_model:
                    logger.error(f"Model {model_id} not found in database, falling back to config")
                    new_orchestrator = OrchestratorAgent(model_id=model_id, user_mcp_toolsets=user_mcp_servers)
                else:
                    use_openrouter = ai_model.provider == "openrouter"
                    # Gateway models use OpenAI-compatible API (not OpenRouter)
                    if ai_model.provider == "gateway":
                        use_openrouter = False
                        logger.info(f"Using Pydantic AI Gateway for model: {ai_model.slug}")
                    new_orchestrator = OrchestratorAgent(
                        model_id=model_id,
                        model_slug=ai_model.slug,
                        use_openrouter=use_openrouter,
                        user_mcp_toolsets=user_mcp_servers
                    )

                # Register domain-specific agents
                new_orchestrator.register_agent("web_search", web_search_agent)
                new_orchestrator.register_agent("vision", va)

                # Return user-specific orchestrator (NOT cached)
                return new_orchestrator

    # Use cached orchestrator if available
    if model_id in orchestrator_cache:
        logger.info(f"Using cached orchestrator for model: {model_id}")
        return orchestrator_cache[model_id]

    # Fetch model from database
    async with db_manager.async_session() as db:
        result = await db.execute(
            select(AIModel).where(AIModel.model_id == model_id)
        )
        ai_model = result.scalar_one_or_none()

    if not ai_model:
        logger.error(f"Model {model_id} not found in database, falling back to config")
        # Fallback to config.models if not in database (backward compatibility)
        new_orchestrator = OrchestratorAgent(model_id=model_id)
    else:
        # Create orchestrator with database model details
        logger.info(f"Creating new orchestrator for model: {model_id} (slug: {ai_model.slug}, provider: {ai_model.provider})")
        use_openrouter = ai_model.provider == "openrouter"
        # Gateway models use OpenAI-compatible API (not OpenRouter)
        if ai_model.provider == "gateway":
            use_openrouter = False
            logger.info(f"Using Pydantic AI Gateway for model: {ai_model.slug}")
        new_orchestrator = OrchestratorAgent(
            model_id=model_id,
            model_slug=ai_model.slug,
            use_openrouter=use_openrouter
        )

    # Register domain-specific agents (same for all orchestrators)
    new_orchestrator.register_agent("web_search", web_search_agent)
    new_orchestrator.register_agent("vision", va)  # Use locally imported vision_agent

    # Cache for future use
    orchestrator_cache[model_id] = new_orchestrator

    return new_orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Initializes agents and database on startup and cleans up on shutdown.
    Also runs the MCP server's lifespan for proper integration.
    """
    global orchestrator, orchestrator_cache, web_search_agent, vision_agent_instance

    logger.info("Initializing database...")

    # Initialize database tables with extended timeout for WSL high-latency networks
    try:
        await asyncio.wait_for(db_manager.create_tables(), timeout=45.0)
        logger.info("Database tables initialized successfully")
    except asyncio.TimeoutError:
        logger.error("Database initialization timed out after 45 seconds (WSL high-latency network)")
        logger.info("Continuing without database - some features may be limited")
        logger.info("Consider using a local PostgreSQL database for WSL development")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Continue anyway - we can work without database

    logger.info("Initializing Nifty Strategist agents...")

    try:
        # Ensure environment variables are loaded for child processes
        load_dotenv(override=True)

        # Debug: Check environment
        has_openrouter = bool(os.environ.get('OPENROUTER_API_KEY'))
        has_openai = bool(os.environ.get('OPENAI_API_KEY'))
        logger.info(f"Environment check - OpenRouter: {has_openrouter}, OpenAI: {has_openai}")

        if not has_openrouter and not has_openai:
            logger.error("WARNING: No API keys found in environment! Check .env file")

        # Initialize domain-specific agents
        web_search_agent = WebSearchAgent()
        from agents.vision_agent import vision_agent as va
        vision_agent_instance = va

        # Initialize default orchestrator
        from config.models import DEFAULT_MODEL_ID
        orchestrator = OrchestratorAgent(model_id=DEFAULT_MODEL_ID)

        # Register domain-specific agents with orchestrator
        orchestrator.register_agent("web_search", web_search_agent)
        orchestrator.register_agent("vision", vision_agent_instance)

        # Cache the default orchestrator
        orchestrator_cache[DEFAULT_MODEL_ID] = orchestrator

        logger.info("All agents initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}")
        raise

    # Yield to allow app to run
    yield

    # Cleanup on shutdown
    logger.info("Shutting down Nifty Strategist...")

    # Close database connections gracefully
    try:
        await db_manager.close()
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")


# Create FastAPI app
app = FastAPI(
    title="Nifty Strategist API",
    description="AI-powered trading assistant for the Indian stock market",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files for generated graphics
uploads_dir = Path(__file__).parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Instrument FastAPI app with Logfire (if enabled)
if logfire_enabled:
    from config import instrument_app
    instrument_app(app)

# Import and configure conversation router with database
from api import conversations, dashboard, memories, tools, runs, upstox_oauth, cockpit
from routes import admin_docs, uploads, admin, auth_routes, hitl, mcp_servers, scratchpad, voice, notes
# Set the database manager in the conversations, memories, runs, auth_routes, and cockpit modules
conversations._db_manager = db_manager
memories._db_manager = db_manager
runs._db_manager = db_manager
auth_routes._db_manager = db_manager
cockpit._db_manager = db_manager
cockpit._upstox_client = shared_upstox_client
# Include conversation router
app.include_router(conversations.router)
# Include runs router (async run completion)
app.include_router(runs.router)
# Include memories router
app.include_router(memories.router)
# Include dashboard router
app.include_router(dashboard.router, prefix="/api/dashboard")
# Include cockpit router (live trading dashboard)
app.include_router(cockpit.router, prefix="/api/cockpit", tags=["cockpit"])
# Include admin docs router
app.include_router(admin_docs.router)
# Include uploads router
app.include_router(uploads.router)
# Include stats router
app.include_router(stats.router)
# Include Admin router (RBAC management + AI Model management)
app.include_router(admin.router)
# Include Auth routes (user info)
app.include_router(auth_routes.router)
# Include HITL (Human-in-the-Loop) router - for trade approvals
app.include_router(hitl.router)
# Include MCP Server Management router
app.include_router(mcp_servers.router)
# Include Tools information router
app.include_router(tools.router)
# Include Upstox OAuth router
app.include_router(upstox_oauth.router)
# Include Scratchpad router
app.include_router(scratchpad.router)
# Include Voice I/O router (STT/TTS)
app.include_router(voice.router)
# Include Notes router
app.include_router(notes.router)

# Configure CORS for frontend
_cors_env = os.getenv("CORS_ORIGINS", "http://localhost:5173")
_cors_origins = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# Add session middleware for OAuth
from starlette.middleware.sessions import SessionMiddleware
session_secret = os.getenv("SESSION_SECRET", os.getenv("JWT_SECRET", "dev-secret-key"))
app.add_middleware(SessionMiddleware, secret_key=session_secret)

# Add cache control middleware to prevent browser caching
from starlette.middleware.base import BaseHTTPMiddleware

class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    Middleware to prevent browser caching for authenticated users.
    Ensures users always see the latest UI/UX without hard refresh.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Always add cache control headers to prevent stale UI
        # This is especially important for:
        # - API responses
        # - Frontend assets (HTML, JS, CSS)
        # - Any dynamic content
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

app.add_middleware(CacheControlMiddleware)


def get_or_create_state(thread_id: str, user_id: str = "default_user") -> ConversationState:
    """Get existing conversation state or create a new one."""
    if thread_id not in conversation_states:
        conversation_states[thread_id] = ConversationState(
            thread_id=thread_id,
            user_id=user_id
        )
    return conversation_states[thread_id]


def get_or_create_conversation(conv_id: str, user_id: str = "default_user") -> str:
    """Get or create a conversation and return its ID"""
    if not conv_id:
        conv_id = f"conv_{uuid.uuid4().hex[:8]}"

    if conv_id not in conversation_messages:
        conversation_messages[conv_id] = []

    return conv_id


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "EspressoBot API",
        "version": "2.0.0",
        "framework": "Pydantic AI",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "architecture": "trading-agent",
        "agents": {
            "orchestrator": orchestrator is not None,
            "web_search": web_search_agent is not None,
            "vision": vision_agent_instance is not None
        },
        "registered_agents": list(orchestrator.specialized_agents.keys()) if orchestrator else [],
        "note": "Nifty Strategist v2 - AI Trading Agent for Indian Stock Market"
    }


@app.get("/api/public/notes/{public_id}")
async def view_public_note(
    public_id: str,
    password: Optional[str] = None
):
    """View a publicly published note (no authentication required)"""
    from sqlalchemy import select
    from database.models import Note, PublishedNote
    from database.session import AsyncSessionLocal
    from datetime import datetime
    import bcrypt
    import markdown

    async with AsyncSessionLocal() as db:
        try:
            # Find published note
            result = await db.execute(
                select(PublishedNote).where(PublishedNote.public_id == public_id)
            )
            published = result.scalar_one_or_none()

            if not published:
                raise HTTPException(status_code=404, detail="Note not found or no longer public")

            # Check if expired
            if published.expires_at and published.expires_at < utc_now_naive():
                raise HTTPException(status_code=410, detail="This note has expired")

            # Check password if required
            if published.password_hash:
                if not password:
                    raise HTTPException(
                        status_code=401,
                        detail="This note is password protected"
                    )
                if not bcrypt.checkpw(password.encode('utf-8'), published.password_hash.encode('utf-8')):
                    raise HTTPException(status_code=401, detail="Incorrect password")

            # Update view count
            published.view_count += 1
            published.last_viewed_at = utc_now_naive()
            await db.commit()

            # Get the note content
            result = await db.execute(
                select(Note).where(Note.id == published.note_id)
            )
            note = result.scalar_one_or_none()

            if not note:
                raise HTTPException(status_code=404, detail="Note content not found")

            # Convert markdown to HTML for display
            md = markdown.Markdown(extensions=['extra', 'codehilite', 'toc', 'tables', 'fenced_code'])
            content_html = md.convert(note.content)

            # Return note data with HTML
            return {
                "title": note.title,
                "content": note.content,
                "content_html": content_html,
                "category": note.category,
                "tags": note.tags or [],
                "created_at": note.created_at.isoformat(),
                "view_count": published.view_count,
                "has_password": published.password_hash is not None
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error viewing public note: {e}")
            raise HTTPException(status_code=500, detail="Failed to load note")


@app.get("/api/test-db")
async def test_db():
    """Test database connection directly"""
    from database.operations import ConversationOps

    async with db_manager.async_session() as session:
        conversations = await ConversationOps.list_conversations(
            session,
            user_id="dev@localhost",
            limit=10,
            offset=0,
            include_archived=False
        )
        return {
            "count": len(conversations),
            "conversations": [
                {"id": c.id, "title": c.title, "user": c.user_id}
                for c in conversations
            ]
        }


@app.post("/api/agent/message")
async def agent_message(request: ChatRequest):
    """
    Main endpoint for the frontend to send messages.
    Supports both regular and streaming responses.
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        # Get or create conversation
        conv_id = get_or_create_conversation(request.conv_id, request.user_id)
        state = get_or_create_state(conv_id, request.user_id)

        # Store user message
        user_msg = ConversationMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role="user",
            content=request.message,
            timestamp=datetime.now().isoformat()
        )

        if conv_id not in conversation_messages:
            conversation_messages[conv_id] = []
        conversation_messages[conv_id].append(user_msg)

        # Process with orchestrator
        response = await orchestrator.orchestrate(request.message, state)

        # Store assistant response
        assistant_msg = ConversationMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            role="assistant",
            content=response,
            timestamp=datetime.now().isoformat(),
            agent=state.last_agent_called
        )
        conversation_messages[conv_id].append(assistant_msg)

        # If streaming is requested, format for SSE
        if request.stream:
            async def generate():
                # Send conversation ID first
                yield f"data: {json.dumps({'conv_id': conv_id, 'event': 'conversation_start'})}\n\n"

                # Send the response in chunks
                words = response.split()
                for i in range(0, len(words), 5):
                    chunk = ' '.join(words[i:i+5]) + ' '
                    yield f"data: {json.dumps({'tokens': [chunk], 'event': 'tokens'})}\n\n"
                    await asyncio.sleep(0.05)  # Small delay for streaming effect

                # Send completion event
                yield f"data: {json.dumps({'event': 'done', 'conv_id': conv_id})}\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Regular response
            return {
                "response": response,
                "conversation_id": conv_id,
                "agent_used": state.last_agent_called,
                "metadata": {
                    "agents_called": state.agents_called,
                    "has_errors": state.last_error is not None
                }
            }

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Get conversation details and messages"""
    if conv_id not in conversation_messages:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = conversation_messages.get(conv_id, [])

    return {
        "id": conv_id,
        "user_id": "default_user",
        "messages": [msg.model_dump() for msg in messages],
        "created_at": messages[0].timestamp if messages else datetime.now().isoformat(),
        "updated_at": messages[-1].timestamp if messages else datetime.now().isoformat(),
        "title": messages[0].content[:50] if messages else "New Conversation"
    }


# DEPRECATED: Using database-backed conversations API instead
# @app.get("/api/conversations")
# async def list_conversations(user_id: str = "default_user"):
#     """List all conversations for a user"""
#     user_convs = []
#
#     for conv_id, messages in conversation_messages.items():
#         if messages:
#             user_convs.append({
#                 "id": conv_id,
#                 "title": messages[0].content[:50] if messages else "New Conversation",
#                 "last_message": messages[-1].content[:100] if messages else "",
#                 "updated_at": messages[-1].timestamp if messages else datetime.now().isoformat(),
#                 "message_count": len(messages)
#             })
#
#     # Sort by updated_at
#     user_convs.sort(key=lambda x: x["updated_at"], reverse=True)
#
#     return user_convs  # Return array directly, not wrapped in object


# DEPRECATED: Using database-backed conversations API instead
# @app.delete("/api/conversations/{conv_id}")
# async def delete_conversation(conv_id: str):
#     """Delete a conversation"""
#     if conv_id in conversation_messages:
#         del conversation_messages[conv_id]
#     if conv_id in conversation_states:
#         del conversation_states[conv_id]
#
#     return {"success": True, "message": "Conversation deleted"}


# DEPRECATED: Using database-backed conversations API instead
# @app.post("/api/conversations/{conv_id}/messages/{msg_id}/edit")
# async def edit_message(conv_id: str, msg_id: str, request: Dict[str, Any]):
#     """Edit a message in a conversation"""
#     if conv_id not in conversation_messages:
#         raise HTTPException(status_code=404, detail="Conversation not found")
#
#     messages = conversation_messages[conv_id]
#     for msg in messages:
#         if msg.id == msg_id:
#             msg.content = request.get("content", msg.content)
#             return {"success": True, "message": "Message updated"}
#
#     raise HTTPException(status_code=404, detail="Message not found")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            if not orchestrator:
                await websocket.send_json({
                    "error": "Orchestrator not initialized"
                })
                continue

            # Process message
            conv_id = get_or_create_conversation(
                data.get("conv_id"),
                data.get("user_id", "default_user")
            )
            state = get_or_create_state(conv_id)

            # Send initial response
            await websocket.send_json({
                "event": "start",
                "conv_id": conv_id
            })

            # Process with orchestrator
            response = await orchestrator.orchestrate(data["message"], state)

            # Send response in chunks for streaming effect
            words = response.split()
            for i in range(0, len(words), 5):
                chunk = ' '.join(words[i:i+5]) + ' '
                await websocket.send_json({
                    "event": "token",
                    "content": chunk
                })
                await asyncio.sleep(0.05)

            # Send completion
            await websocket.send_json({
                "event": "done",
                "conv_id": conv_id,
                "agent_used": state.last_agent_called
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


# Legacy compatibility endpoints
@app.post("/api/chat")
async def chat_legacy(request: ChatRequest):
    """Legacy chat endpoint - redirects to new agent/message endpoint"""
    return await agent_message(request)


# Authentication endpoints
class LoginRequest(BaseModel):
    """Login request model"""
    email: str
    password: str


class RegisterRequest(BaseModel):
    """Registration request model"""
    email: str
    password: str
    name: str


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """
    Email/password login endpoint.
    Returns JWT token on successful authentication.
    """
    from database.models import User as DBUser, Role, Permission
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import bcrypt

    async with db_manager.async_session() as db:
        # Find user by email with roles and permissions eagerly loaded
        stmt = (
            select(DBUser)
            .where(DBUser.email == request.email)
            .options(
                selectinload(DBUser.roles).selectinload(Role.permissions)
            )
        )
        result = await db.execute(stmt)
        db_user = result.scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        if not db_user.password_hash:
            raise HTTPException(status_code=401, detail="Password not set for this account")

        if not bcrypt.checkpw(request.password.encode(), db_user.password_hash.encode()):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Get user permissions from roles (already loaded)
        permissions = []
        for role in db_user.roles:
            for perm in role.permissions:
                if perm.name not in permissions:
                    permissions.append(perm.name)

        # Create JWT token
        user_data = {
            "id": db_user.id,
            "email": db_user.email,
            "name": db_user.name or db_user.email.split("@")[0],
            "permissions": permissions
        }
        token = create_access_token(user_data)

        logger.info(f"[Auth] User {db_user.email} logged in successfully with permissions: {permissions}")

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user_data
        }


@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """
    User registration endpoint.
    Creates new user and returns JWT token.
    """
    from database.models import User as DBUser, Role, Permission
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import bcrypt

    try:
        async with db_manager.async_session() as db:
            # Check if user already exists
            stmt = select(DBUser).where(DBUser.email == request.email)
            result = await db.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                raise HTTPException(status_code=400, detail="Email already registered")

            # Hash password
            password_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()

            # Create new user
            new_user = DBUser(
                email=request.email,
                name=request.name,
                password_hash=password_hash,
                is_active=True
            )
            db.add(new_user)

            # Flush to get the new user's ID before assigning roles
            await db.flush()

            # Assign default 'new_user' role (pending activation, no permissions)
            role_stmt = select(Role).where(Role.name == "new_user").options(selectinload(Role.permissions))
            role_result = await db.execute(role_stmt)
            user_role = role_result.scalar_one_or_none()

            permissions = []
            if user_role:
                # Insert into association table directly to avoid lazy-load issue
                from database.models import user_roles
                await db.execute(user_roles.insert().values(user_id=new_user.id, role_id=user_role.id))
                # Get permissions while role is still attached to session
                for perm in user_role.permissions:
                    permissions.append(perm.name)

            await db.commit()

            # Create JWT token
            user_data = {
                "id": new_user.id,
                "email": new_user.email,
                "name": new_user.name,
                "permissions": permissions
            }
            token = create_access_token(user_data)

            logger.info(f"[Auth] New user registered: {new_user.email} with permissions: {permissions}")

            return {
                "access_token": token,
                "token_type": "bearer",
                "user": user_data
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auth] Registration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Registration failed. Please try again later.")


@app.get("/api/auth/dev-login")
async def dev_login():
    """
    Development login endpoint - creates a dev token without password.
    Only works when ENVIRONMENT=development.
    """
    if os.getenv("ENVIRONMENT") != "development":
        raise HTTPException(status_code=403, detail="Dev login only available in development mode")

    # Create dev user token
    user_data = {
        "id": 999,
        "email": "dev@localhost",
        "name": "Dev User",
        "permissions": [
            "chat.access",
            "dashboard.access",
            "memory.access",
            "settings.access",
        ]
    }
    token = create_access_token(user_data)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_data
    }


@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user_optional)):
    """
    Get current authenticated user.
    Returns mock user in development if not authenticated.
    Also includes access control information.
    Fetches fresh data from database to ensure bio and other fields are up-to-date.
    """
    if not user:
        # Return development user
        user = User(
            id=1,
            email="dev@localhost",
            name="Development User"
        )

    # Fetch fresh user data from database to get latest bio, name, etc.
    from database.models import User as DBUser

    logger.info(f"[get_me] Fetching user from DB, user.id={user.id}")
    async with db_manager.async_session() as db:
        db_user = await db.get(DBUser, user.id)
        logger.debug(f"[get_me] DB query result: db_user={db_user}, bio={db_user.bio if db_user else 'N/A'}")
        if db_user:
            # Update user object with fresh database data
            user = User(
                id=db_user.id,
                email=db_user.email,
                name=db_user.name,
                bio=db_user.bio,
                picture=db_user.profile_picture,
                permissions=user.permissions  # Keep permissions from JWT
            )
            logger.debug(f"[get_me] Updated user object, bio={user.bio}")

    # Check if user is in allowed emails
    allowed_emails = os.getenv("ALLOWED_EMAILS", "").split(",")
    allowed_emails = [email.strip() for email in allowed_emails if email.strip()]
    is_allowed = user.email in allowed_emails or user.email == "dev@localhost"

    # Return user with additional access info
    user_dict = user.model_dump()
    user_dict["hasAccess"] = is_allowed
    user_dict["is_whitelisted"] = is_allowed  # Frontend expects this field
    user_dict["allowedEmails"] = allowed_emails if not is_allowed else []

    return user_dict


@app.post("/api/auth/logout")
async def logout():
    """Logout endpoint (client should clear token)"""
    return {"status": "success", "message": "Logged out successfully"}


# Trading API endpoints
@app.get("/api/portfolio")
async def get_portfolio(user: User = Depends(get_current_user)):
    """
    Get the current portfolio summary for the dashboard.
    Returns portfolio value, positions, and P&L.
    """
    try:
        portfolio = await shared_upstox_client.get_portfolio()

        return {
            "total_value": portfolio.total_value,
            "available_cash": portfolio.available_cash,
            "invested_value": portfolio.invested_value,
            "day_pnl": portfolio.day_pnl,
            "day_pnl_percentage": portfolio.day_pnl_percentage,
            "total_pnl": portfolio.total_pnl,
            "total_pnl_percentage": portfolio.total_pnl_percentage,
            "positions": [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "average_price": pos.average_price,
                    "current_price": pos.current_price,
                    "pnl": pos.pnl,
                    "pnl_percentage": pos.pnl_percentage,
                    "day_change": pos.day_change,
                    "day_change_percentage": pos.day_change_percentage,
                }
                for pos in portfolio.positions
            ],
            "paper_trading": shared_upstox_client.paper_trading,
            "market_status": "Paper Trading Mode" if shared_upstox_client.paper_trading else "Live",
        }
    except Exception as e:
        logger.error(f"Error fetching portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/positions")
async def get_positions(user: User = Depends(get_current_user)):
    """Get all open positions."""
    try:
        portfolio = await shared_upstox_client.get_portfolio()
        return {
            "positions": [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "average_price": pos.average_price,
                    "current_price": pos.current_price,
                    "pnl": pos.pnl,
                    "pnl_percentage": pos.pnl_percentage,
                }
                for pos in portfolio.positions
            ],
            "count": len(portfolio.positions),
        }
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/trades")
async def get_trade_history(
    limit: int = 50,
    user: User = Depends(get_current_user)
):
    """Get trade history for the current user."""
    try:
        from services.trade_persistence import get_trade_persistence
        persistence = get_trade_persistence()

        if not persistence:
            raise HTTPException(status_code=500, detail="Trade persistence not initialized")

        trades = await persistence.get_trade_history(user.id, limit=limit)
        return {
            "trades": trades,
            "count": len(trades),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/clear-model-cache")
async def clear_model_cache(user: User = Depends(requires_permission("admin.manage_users"))):
    """Clear orchestrator model cache (superadmin only)"""
    global orchestrator_cache

    cache_keys = list(orchestrator_cache.keys())
    orchestrator_cache.clear()

    logger.info(f"Cleared orchestrator cache for models: {cache_keys}")

    return {
        "status": "success",
        "message": f"Cleared cache for {len(cache_keys)} models",
        "cleared_models": cache_keys
    }


# User Profile endpoints
@app.get("/api/models")
async def get_available_models():
    """Get list of available orchestrator models (enabled only)"""
    from database.models import AIModel
    from sqlalchemy import select

    try:
        async with db_manager.async_session() as db:
            # Fetch only enabled models, ordered by default first then by name
            result = await db.execute(
                select(AIModel)
                .where(AIModel.is_enabled == True)
                .order_by(AIModel.is_default.desc(), AIModel.name)
            )
            db_models = result.scalars().all()

            # Convert to dict format expected by frontend
            models = [
                {
                    "id": m.model_id,
                    "name": m.name,
                    "slug": m.slug,
                    "provider": m.provider,
                    "description": m.description,
                    "context_window": m.context_window,
                    "max_output": m.max_output,
                    "cost_input": m.cost_input,
                    "cost_output": m.cost_output,
                    "supports_thinking": m.supports_thinking,
                    "speed": m.speed,
                    "intelligence": m.intelligence,
                    "recommended_for": m.recommended_for or []
                }
                for m in db_models
            ]

            return {"models": models}
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch available models")


@app.get("/api/user/model-preference")
async def get_user_model_preference(user: User = Depends(get_current_user_optional)):
    """Get user's preferred model"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        from database.models import User as DBUser
        from config.models import DEFAULT_MODEL_ID

        async with db_manager.async_session() as db:
            db_user = await db.get(DBUser, user.id)
            if db_user:
                return {
                    "preferred_model": db_user.preferred_model or DEFAULT_MODEL_ID
                }
            else:
                raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error(f"Failed to get model preference: {e}")
        raise HTTPException(status_code=500, detail="Failed to get model preference")


@app.put("/api/user/model-preference")
async def update_user_model_preference(request: Request, user: User = Depends(get_current_user_optional)):
    """Update user's preferred model"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        data = await request.json()
        model_id = data.get("preferred_model")

        if not model_id:
            raise HTTPException(status_code=400, detail="preferred_model is required")

        from database.models import User as DBUser, AIModel
        from sqlalchemy import select

        async with db_manager.async_session() as db:
            # Validate model ID exists in database and is enabled
            result = await db.execute(
                select(AIModel).where(
                    AIModel.model_id == model_id,
                    AIModel.is_enabled == True
                )
            )
            ai_model = result.scalar_one_or_none()
            if not ai_model:
                raise HTTPException(status_code=400, detail=f"Invalid or disabled model ID: {model_id}")

            # Update user preference
            db_user = await db.get(DBUser, user.id)
            if db_user:
                db_user.preferred_model = model_id
                await db.commit()
                await db.refresh(db_user)

                logger.info(f"User {user.email} switched to model: {model_id}")

                return {
                    "preferred_model": db_user.preferred_model,
                    "message": "Model preference updated successfully"
                }
            else:
                raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update model preference: {e}")
        raise HTTPException(status_code=500, detail="Failed to update model preference")


@app.put("/api/user/profile")
async def update_user_profile(request: Request, user: User = Depends(get_current_user_optional)):
    """Update user profile information"""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        data = await request.json()

        # Import User model from database
        from database.models import User as DBUser

        # Update user profile
        async with db_manager.async_session() as db:
            db_user = await db.get(DBUser, user.id)
            if db_user:
                if 'name' in data:
                    db_user.name = data['name']
                if 'email' in data:
                    db_user.email = data['email']
                if 'bio' in data:
                    db_user.bio = data['bio']

                await db.commit()
                await db.refresh(db_user)

                # Return updated user data
                return {
                    "id": db_user.id,
                    "email": db_user.email,
                    "name": db_user.name,
                    "bio": db_user.bio,
                    "picture": db_user.profile_picture,
                    "hasAccess": True,
                    "is_whitelisted": db_user.is_whitelisted
                }
            else:
                raise HTTPException(status_code=404, detail="User not found")

    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")


# Memory endpoints (stub for now)
@app.get("/api/memory/list/{user_id}")
async def list_memories(user_id: int, limit: int = 100):
    """List memory entries for a user (stub for now)"""
    # TODO: Implement actual memory storage
    return []


# Agent log endpoint (for frontend logging)
@app.post("/api/agent/log")
async def agent_log(request: Request):
    """Log endpoint for frontend debugging"""
    try:
        data = await request.json()
        logger.info(f"Frontend log: {data}")
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Log error: {e}")
        return {"status": "error", "message": str(e)}


# Async message endpoints (stub for now - will implement async later)
@app.post("/api/agent/async/message")
async def agent_async_message(request: ChatRequest):
    """Async version of agent message endpoint"""
    # For now, just redirect to the regular message endpoint
    # TODO: Implement proper async handling
    return await agent_message(request)


@app.post("/api/agent/sse")
async def agent_sse(request: ChatRequest):
    """SSE version of agent message endpoint"""
    # For now, just redirect to the regular message endpoint
    request.stream = True
    return await agent_message(request)


async def process_and_track_run(
    stream_generator,
    run_id: str,
    thread_id: str,
    user_id: str,
    client_queue: Optional[asyncio.Queue] = None
):
    """
    Process an SSE stream in the background with run tracking.
    
    This ensures:
    1. Run status is updated as stream progresses
    2. Results are captured and saved to database
    3. Stream continues even if client disconnects
    4. Client receives events via queue if connected
    
    Args:
        stream_generator: The original SSE stream generator
        run_id: Run ID for tracking
        thread_id: Conversation thread ID
        user_id: User ID
        client_queue: Optional queue to push events to for the client
    """
    from services.run_manager import run_manager
    from database.models import Run
    
    logger.info(f"[Runs] Starting background processing for run {run_id}")
    
    # Track run status
    from sqlalchemy import update
    async with db_manager.async_session() as session:
        await session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(status="in_progress", started_at=utc_now_naive())
        )
        await session.commit()
        
    # Register this task with RunManager so it can be cancelled if needed
    current_task = asyncio.current_task()
    if current_task:
        async with db_manager.async_session() as session:
            await run_manager.start_run(run_id, session, current_task)

    # Capture response data
    captured_text = []
    captured_tool_calls = []
    captured_reasoning = None
    captured_todos = []
    has_error = False
    error_message = None
    
    try:
        async for chunk in stream_generator:
            # Push to client queue if available
            if client_queue:
                await client_queue.put(chunk)
                
            # Parse and capture data
            try:
                chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                
                if chunk_str.startswith('data: '):
                    data_str = chunk_str[6:].strip()
                    if data_str and data_str != '[DONE]':
                        event = json.loads(data_str)
                        event_type = event.get('type', '')
                        
                        # Capture text content
                        if event_type == 'TEXT_MESSAGE_CONTENT':
                            delta = event.get('delta', '')
                            if delta:
                                captured_text.append(delta)
                                
                        # Capture tool calls
                        elif event_type == 'TOOL_CALL':
                            tool_data = event.get('data', {})
                            captured_tool_calls.append(tool_data)
                            
                        # Capture reasoning
                        elif event_type == 'THINKING_CONTENT':
                            reasoning_delta = event.get('delta', '')
                            if reasoning_delta:
                                if captured_reasoning is None:
                                    captured_reasoning = reasoning_delta
                                else:
                                    captured_reasoning += reasoning_delta
                                    
                        # Capture TODO updates
                        elif event_type == 'TODO_UPDATE':
                            todos = event.get('todos', [])
                            if todos:
                                captured_todos = todos
                                
                        # Capture errors
                        elif event_type == 'ERROR':
                            has_error = True
                            error_message = event.get('error', 'Unknown error')
                            
            except json.JSONDecodeError:
                pass  # Ignore non-JSON chunks
            except Exception as e:
                logger.error(f"[Runs] Error parsing chunk: {e}")
                
        # Stream completed successfully
        logger.info(f"[Runs] Background stream completed for run {run_id}")
        
        # Signal completion to client
        if client_queue:
            await client_queue.put(None)
            
        # Save results to database
        result_data = {
            "text": ''.join(captured_text),
            "tool_calls": captured_tool_calls,
            "reasoning": captured_reasoning,
            "todos": captured_todos
        }
        
        async with db_manager.async_session() as session:
            await run_manager.complete_run(
                run_id,
                session,
                result=result_data,
                error=error_message if has_error else None
            )
            
        logger.info(f"[Runs] Saved results for run {run_id}")
        
        # Log agent response to Logfire for observability
        response_text = ''.join(captured_text)
        if response_text:
            log_agent_response(
                thread_id=thread_id,
                user_id=user_id,
                response=response_text,
                model=None,  # Model info not available here
                tokens_used=None,  # Token info not available here
                metadata={
                    'run_id': run_id,
                    'tool_calls': len(captured_tool_calls),
                    'has_error': has_error
                }
            )
            
    except asyncio.CancelledError:
        logger.info(f"[Runs] Run {run_id} cancelled")
        # Signal error to client if queue exists
        if client_queue:
            await client_queue.put(None) # End stream
            
        # Mark run as cancelled
        async with db_manager.async_session() as session:
            await run_manager.cancel_run(run_id, session)
            
        raise
        
    except Exception as e:
        logger.error(f"[Runs] Error in background stream for run {run_id}: {e}", exc_info=True)
        
        # Signal error to client
        if client_queue:
            # Create error event
            error_event = {
                "type": "ERROR",
                "error": str(e)
            }
            await client_queue.put(f"data: {json.dumps(error_event)}\\n\\n".encode())
            await client_queue.put(None)
            
        # Mark run as failed
        async with db_manager.async_session() as session:
            await run_manager.complete_run(
                run_id,
                session,
                result={
                    "text": ''.join(captured_text),
                    "tool_calls": captured_tool_calls,
                    "partial": True
                },
                error=str(e)
            )


async def stream_from_queue(queue: asyncio.Queue):
    """Yield items from a queue until None is received"""
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


@app.post("/api/agent/ag-ui")
async def agent_ag_ui(request: Request, user: User = Depends(get_current_user_optional)):
    """
    AG-UI protocol endpoint for optimized streaming with Pydantic AI.
    Provides real-time token streaming with consistent behavior between CLI and web.
    This ensures the same agent behavior as CLI mode.
    """
    if not HAS_AG_UI:
        raise HTTPException(
            status_code=501,
            detail="AG-UI not available. Install with: pip install 'pydantic-ai-slim[ag-ui]'"
        )

    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    try:
        # Parse the request to get thread_id
        body = await request.json()
        # Handle None/null threadId from frontend (use 'or' to catch None, empty string, etc.)
        thread_id = body.get("threadId") or f"ag_ui_{uuid.uuid4().hex[:8]}"

        # Get user's preferred model
        from database.models import User as DBUser
        from config.models import DEFAULT_MODEL_ID

        preferred_model = DEFAULT_MODEL_ID
        user_upstox_token = None  # Decrypted live token for CLI tools
        user_trading_mode = "paper"  # Default to paper, updated from DB below
        if user:
            async with db_manager.async_session() as db:
                db_user = await db.get(DBUser, user.id)
                if db_user:
                    user_trading_mode = db_user.trading_mode or "paper"
                    if db_user.preferred_model:
                        preferred_model = db_user.preferred_model
                        logger.info(f"Using user's preferred model: {preferred_model}")
                    # Resolve live Upstox token if user is in live trading mode
                    if (db_user.trading_mode == "live"
                            and db_user.upstox_access_token
                            and db_user.upstox_token_expiry
                            and db_user.upstox_token_expiry > datetime.utcnow()):
                        from utils.encryption import decrypt_token
                        user_upstox_token = decrypt_token(db_user.upstox_access_token)
                        if user_upstox_token:
                            logger.info(f"Chat: live Upstox token resolved for user {user.id}")
                        else:
                            logger.warning(f"Chat: token decrypt failed for user {user.id}")

        # Get orchestrator for this model (creates if not cached, loads user MCP servers if configured)
        user_orchestrator = await get_orchestrator_for_model(preferred_model, user_id=user.id if user else None)

        # Track conversation in mock database
        messages = body.get("messages", [])

        # Check if we need to process images for vision-capable models
        # We'll handle this separately from AG-UI since BinaryContent isn't JSON-serializable
        vision_prompt = None
        original_text_content = None

        if messages:
            user_messages_list = [i for i, m in enumerate(messages) if m.get("role") == "user"]
            if user_messages_list:
                last_user_idx = user_messages_list[-1]
                last_user_message = messages[last_user_idx]
                original_text_content = last_user_message.get("content", "")

                # Process message for vision capability
                processed_content = await process_message_with_vision(
                    original_text_content,
                    preferred_model
                )

                # If processed_content is a list (contains BinaryContent), we have vision data
                if isinstance(processed_content, list):
                    vision_prompt = processed_content
                    logger.info("[Vision] Detected vision content - will bypass AG-UI and call agent directly")

        # Note: Context window management is now handled by Pydantic AI's history_processors
        # in orchestrator.py via sliding_window_history_processor()
        if messages:
            # Get the last user message (use original text content for DB/memory, not BinaryContent)
            user_messages = [m for m in messages if m.get("role") == "user"]
            if user_messages:
                # Use original_text_content if we have vision data, otherwise get from message
                last_message = original_text_content if original_text_content else user_messages[-1].get("content", "")
                # Use user email or default for dev mode
                user_email = user.email if user else "dev@localhost"
                # Save to database asynchronously
                await save_conversation_to_db(thread_id, user_email, last_message)
                logger.info(f"Created/updated conversation {thread_id} for user {user_email}")

                # Note: Enhanced log_user_message call with full context happens later
                # after we retrieve user_memories, hitl_enabled, use_todo, etc.

        # Create a Run record for tracking async execution
        from services.run_manager import run_manager
        run_id = None
        if messages and user:
            user_messages = [m for m in messages if m.get("role") == "user"]
            if user_messages:
                last_message_content = original_text_content if original_text_content else user_messages[-1].get("content", "")
                async with db_manager.async_session() as session:
                    run_id = await run_manager.create_run(
                        session,
                        thread_id=thread_id,
                        user_id=str(user.id),
                        user_message=last_message_content,
                        metadata={"model": preferred_model}
                    )
                logger.info(f"[Runs] Created run {run_id} for thread {thread_id}")

        # Get or create conversation state based on thread_id
        if thread_id in conversation_states:
            state = conversation_states[thread_id]
        else:
            state = ConversationState(
                thread_id=thread_id,
                user_id=user.email if user else "anonymous"
            )
            conversation_states[thread_id] = state

        # Retrieve user memories for context injection using semantic search
        user_email = user.email if user else "anonymous"
        # Get the current user message for semantic search (use original text, not BinaryContent)
        current_message = None
        if messages:
            user_messages = [m for m in messages if m.get("role") == "user"]
            if user_messages:
                # Use original_text_content if we have vision data, otherwise get from message
                current_message = original_text_content if original_text_content else user_messages[-1].get("content", "")

        user_memories = await get_user_memories_for_context(
            user_email,
            current_message=current_message,
            limit=10,
            similarity_threshold=0.35  # Lower threshold to catch question-answer pairs
        )

        if user_memories:
            logger.info(f"Injected {len(user_memories)} memories for user {user_email}")

        # Load HITL (Human-in-the-Loop) preference
        hitl_enabled = False
        if user:
            try:
                from sqlalchemy import select
                from database.models import UserPreference

                async with db_manager.async_session() as session:
                    stmt = select(UserPreference).where(UserPreference.user_id == str(user.id))
                    result = await session.execute(stmt)
                    prefs = result.scalar_one_or_none()
                    if prefs:
                        hitl_enabled = prefs.hitl_enabled
                        logger.info(f"[HITL] User {user.email} has HITL {'enabled' if hitl_enabled else 'disabled'}")
            except Exception as e:
                logger.error(f"Error loading HITL preference: {e}")

        # Get TODO mode preference from request
        preferences = body.get("preferences", {})
        use_todo = preferences.get("use_todo", False)
        if use_todo:
            logger.info(f"[TODO] User enabled TODO mode for this conversation")

        # Remove preferences from body before passing to AG-UI handler
        # (AG-UI schema doesn't include this field)
        body.pop("preferences", None)

        # Register stream for interruption support using run_id (not thread_id)
        # This ensures each connection has its own isolated stream
        from utils.interrupt_manager import get_interrupt_manager
        interrupt_mgr = get_interrupt_manager()
        stream_key = run_id if run_id else thread_id  # Use run_id for isolation, fallback to thread_id
        interrupt_signal = interrupt_mgr.register_stream(stream_key)
        logger.info(f"[Interrupt] Registered interrupt signal for stream {stream_key} (run_id={run_id}, thread_id={thread_id})")

        # Fetch paper trading portfolio for dynamic context (only in paper mode)
        paper_total_value = None
        paper_total_pnl = None
        paper_pnl_percent = None

        if user and user_trading_mode == "paper":
            try:
                # Use the global trade_persistence instance
                if trade_persistence:
                    portfolio = await trade_persistence.get_portfolio_for_user(user.id)
                    paper_total_value = portfolio.total_value
                    paper_total_pnl = portfolio.total_pnl
                    paper_pnl_percent = portfolio.total_pnl_percentage
                    logger.info(f"[Paper] Loaded portfolio for user {user.id}: ₹{paper_total_value:,.2f}")
            except Exception as e:
                logger.error(f"Error loading paper portfolio for context: {e}")

        # Create dependencies for the orchestrator
        deps = OrchestratorDeps(
            state=state,
            available_agents=user_orchestrator.specialized_agents,
            user_memories=user_memories,
            user_name=user.name if user else None,
            user_bio=user.bio if user else None,
            hitl_enabled=hitl_enabled,
            use_todo=use_todo,
            interrupt_signal=interrupt_signal,
            upstox_access_token=user_upstox_token,
            user_id=user.id if user else None,
            paper_total_value=paper_total_value,
            paper_total_pnl=paper_total_pnl,
            paper_pnl_percent=paper_pnl_percent,
        )
        logger.info(f"[TODO] Created OrchestratorDeps with use_todo={deps.use_todo}")

        # Log user message with full context to Logfire (after gathering all context)
        log_user_message(
            thread_id=thread_id,
            user_id=user.email if user else "anonymous",
            message=current_message if current_message else str(messages),
            has_images=vision_prompt is not None,
            model=user_orchestrator.model_id if hasattr(user_orchestrator, 'model_id') else preferred_model,
            metadata={
                'run_id': run_id,
                'hitl_enabled': hitl_enabled,
                'use_todo': use_todo,
                'user_email': user.email if user else "anonymous",
                'message_count': len(messages) if messages else 0
            },
            context={
                'user_memories': user_memories,
                'user_name': user.name if user else None,
                'user_bio': user.bio if user else None,
                'hitl_enabled': hitl_enabled,
                'use_todo': use_todo,
                'available_agents': user_orchestrator.specialized_agents,
            },
            conversation_history=messages  # Full conversation for context tracking
        )

        # Check if we have vision content - if so, bypass AG-UI and call agent directly
        if vision_prompt is not None:
            logger.info("[Vision] Calling agent directly with image path (bypassing AG-UI)")

            # Call the agent directly with vision prompt
            async def vision_stream_generator():
                """Stream agent response with vision content as AG-UI events"""
                import json
                import uuid

                try:
                    # Send initial events (using custom event for routing)
                    yield f"data: {json.dumps({'type': 'AGENT_ROUTING', 'agent': 'orchestrator'})}\n\n"

                    message_id = f"msg_{uuid.uuid4().hex[:12]}"
                    # AG-UI protocol: flat structure with camelCase fields
                    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_START', 'messageId': message_id})}\n\n"

                    # Call agent with text prompt containing image reference
                    async with user_orchestrator.agent.run_stream(
                        vision_prompt,  # String with embedded image path: "[Image uploaded: /path]"
                        deps=deps
                    ) as stream:
                        # Stream text chunks using AG-UI TEXT_MESSAGE_CONTENT event
                        # Note: stream.stream_text() gives cumulative text, we need to calculate deltas
                        previous_text = ""
                        async for chunk in stream.stream_text():
                            # Calculate delta (only new text since last chunk)
                            delta = chunk[len(previous_text):]
                            if delta:
                                yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': message_id, 'delta': delta})}\n\n"
                            previous_text = chunk

                    # Send completion events
                    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_END', 'messageId': message_id})}\n\n"
                    yield f"data: {json.dumps({'type': 'RUN_FINISHED'})}\n\n"

                except Exception as e:
                    logger.error(f"[Vision] Error streaming vision response: {e}", exc_info=True)
                    # Send error event (custom format)
                    error_event = {
                        "type": "ERROR",
                        "message": f"Vision analysis error: {str(e)}"
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            # Wrap with run tracking if we have a run_id
            vision_stream = vision_stream_generator()
            if run_id:
                client_queue = asyncio.Queue()
                # Start background task
                asyncio.create_task(process_and_track_run(
                    vision_stream,
                    run_id=run_id,
                    thread_id=thread_id,
                    user_id=str(user.id) if user else "anonymous",
                    client_queue=client_queue
                ))
                vision_stream = stream_from_queue(client_queue)

            # Return streaming response with run tracking
            headers = {
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
            if run_id:
                headers["X-Run-ID"] = run_id

            return StreamingResponse(
                vision_stream,
                media_type="text/event-stream",
                headers=headers
            )

        # Standard AG-UI handler for all models
        # With OpenRouterProvider, DeepSeek reasoning field is automatically parsed
        # into ThinkingPart objects, and AG-UI adapter emits THINKING events
        import json

        # Create a mock request with the body for the handler
        class MockRequest:
            def __init__(self, body_dict):
                self.body_dict = body_dict
                # Add headers attribute for AG-UI handler compatibility
                self.headers = {
                    'content-type': 'application/json',
                    'accept': 'text/event-stream'
                }

            async def json(self):
                return self.body_dict

            async def body(self):
                return json.dumps(self.body_dict).encode()

        mock_request = MockRequest(body)

        # Get the response from enhanced AG-UI handler with interrupt support
        # Note: Primary context management via history_processors in orchestrator.py
        # Middle-out transform provides secondary safety layer at API level
        response = await enhanced_handle_ag_ui_request(
            user_orchestrator.agent,
            mock_request,
            deps=deps,
            model_settings={
                'temperature': 1,
                'transforms': ['middle-out']  # OpenRouter fallback compression (belt-and-suspenders)
            },
            thread_id=stream_key  # Use run_id for stream isolation, not thread_id
        )

        # If it's a streaming response, wrap it to capture the assistant's response
        if hasattr(response, 'body_iterator'):
            # Create response capture with database save callback
            capturer = ResponseCapture(
                on_complete=save_assistant_message_to_db
            )

            # Get the user message for token estimation
            user_input_for_tokens = ""
            if messages:
                user_messages = [m for m in messages if m.get("role") == "user"]
                if user_messages:
                    user_input_for_tokens = user_messages[-1].get("content", "")

            # Wrap the stream to capture response (with user message for token estimation)
            captured_stream = capturer.capture_stream(
                response.body_iterator,
                thread_id,
                input_content=user_input_for_tokens
            )

            # Wrap with run tracking if we have a run_id
            if run_id:
                client_queue = asyncio.Queue()
                # Start background task
                asyncio.create_task(process_and_track_run(
                    captured_stream,
                    run_id=run_id,
                    thread_id=thread_id,
                    user_id=str(user.id) if user else "anonymous",
                    client_queue=client_queue
                ))
                tracked_stream = stream_from_queue(client_queue)
            else:
                tracked_stream = captured_stream

            # Return new streaming response with capture and run tracking
            # Include run_id in headers so frontend can poll for status
            response_headers = dict(response.headers) if hasattr(response, 'headers') else {}
            if run_id:
                response_headers['X-Run-ID'] = run_id

            return StreamingResponse(
                tracked_stream,
                media_type=response.media_type,
                headers=response_headers
            )

        return response
    except Exception as e:
        logger.error(f"AG-UI error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/interrupt")
async def agent_interrupt(request: Request, user: User = Depends(get_current_user_optional)):
    """
    Interrupt current agent operation.

    Gracefully cancels the active stream and preserves partial progress.
    Queued messages will be processed after interruption.
    """
    try:
        from utils.interrupt_manager import get_interrupt_manager

        body = await request.json()
        thread_id = body.get("threadId")
        reason = body.get("reason", "User requested stop")

        if not thread_id:
            raise HTTPException(status_code=400, detail="threadId required")

        # Get interrupt manager
        interrupt_mgr = get_interrupt_manager()

        # Send interrupt signal
        # First try interrupting the thread directly (legacy/fallback)
        interrupted = interrupt_mgr.interrupt(thread_id, reason)

        if not interrupted:
            # If not found, check for active runs associated with this thread
            from services.run_manager import run_manager
            
            # We need to find the active run for this thread
            # Since we don't have the run_id from the frontend, we have to look it up
            # This is a bit of a hack, ideally frontend should send run_id
            async with db_manager.async_session() as session:
                runs = await run_manager.get_active_runs_for_user(str(user.id) if user else "anonymous", session)
                
                for run in runs:
                    if run["thread_id"] == thread_id:
                        # Found active run for this thread
                        run_id = run["id"]
                        logger.info(f"[Interrupt] Found active run {run_id} for thread {thread_id}, interrupting...")
                        interrupted = interrupt_mgr.interrupt(run_id, reason)
                        if interrupted:
                            break

        if interrupted:
            # Update conversation state
            if thread_id in conversation_states:
                state = conversation_states[thread_id]
                state.is_interrupted = True
                state.interrupted_at = datetime.now()
                state.interrupt_reason = reason

            logger.info(f"[Interrupt] Successfully interrupted {thread_id}: {reason}")
            return {
                "status": "success",
                "message": f"Operation interrupted: {reason}",
                "threadId": thread_id
            }
        else:
            logger.warning(f"[Interrupt] No active stream for {thread_id}")
            return {
                "status": "warning",
                "message": "No active operation to interrupt",
                "threadId": thread_id
            }

    except Exception as e:
        logger.error(f"Interrupt error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/approve")
async def agent_approve(request: Request):
    """Approve agent action"""
    data = await request.json()
    logger.info(f"Approval received: {data}")
    return {"status": "approved"}


@app.post("/api/agent/reject")
async def agent_reject(request: Request):
    """Reject agent action"""
    data = await request.json()
    logger.info(f"Rejection received: {data}")
    return {"status": "rejected"}


@app.get("/api/agent/status")
async def agent_status():
    """Get status of all agents"""
    return {
        "architecture": "trading-agent",
        "agents": {
            "orchestrator": {
                "initialized": orchestrator is not None,
                "model": "deepseek/deepseek-chat",
                "registered_agents": list(orchestrator.specialized_agents.keys()) if orchestrator else []
            },
            "web_search": {
                "initialized": web_search_agent is not None,
                "type": "domain-specific (Perplexity API)"
            },
            "vision": {
                "initialized": vision_agent_instance is not None,
                "type": "domain-specific (multimodal)"
            }
        },
        "tools": {
            "trading": ["get_quote", "analyze_symbol", "get_portfolio", "place_order", "watchlist"],
            "domain_agents": ["web_search", "vision"]
        },
        "note": "Nifty Strategist v2 - AI Trading Agent with HITL approval for trades"
    }


# A2UI Interaction Models - Supports both legacy and v0.8 spec formats
class A2UIInteraction(BaseModel):
    """
    A2UI interaction request from frontend

    A2UI v0.8 spec (userAction):
    - name: Action name (e.g., "submit", "search")
    - surface_id: Surface ID
    - source_component_id: Component ID that triggered action
    - timestamp: ISO 8601 timestamp
    - context: Form data / resolved context

    Legacy format (for backwards compatibility):
    - action: Same as 'name'
    - payload: Same as 'context'
    - component_id: Same as 'source_component_id'
    """
    thread_id: str

    # A2UI v0.8 spec fields
    name: Optional[str] = None
    source_component_id: Optional[str] = None
    timestamp: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    # Legacy fields (backwards compatibility)
    action: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    component_id: Optional[str] = None
    surface_id: Optional[str] = None


@app.post("/api/agent/a2ui-interaction")
async def handle_a2ui_interaction(
    interaction: A2UIInteraction,
    current_user: User = Depends(get_current_user)
):
    """
    Handle A2UI button clicks, form submissions, and other interactions.
    Supports both A2UI v0.8 spec (userAction) and legacy format.

    When a user interacts with an A2UI component (clicks a button, submits a form),
    the frontend calls this endpoint. The interaction is then injected into the
    next agent message processing for that thread.
    """
    try:
        # Normalize to spec format (accept both legacy and v0.8)
        action_name = interaction.name or interaction.action or "unknown"
        action_context = interaction.context or interaction.payload or {}
        component_id = interaction.source_component_id or interaction.component_id
        surface_id = interaction.surface_id

        logger.info(f"[A2UI] userAction received: name={action_name}, thread={interaction.thread_id}")
        logger.info(f"[A2UI] Context: {action_context}")

        # Store interaction for processing by next agent call
        # For now, we'll convert to a user message that the agent can process
        # In the future, this could be a dedicated interaction queue

        # Create a synthetic user message describing the interaction
        action_description = f"[A2UI Interaction] User clicked '{action_name}'"
        if action_context:
            action_description += f" with data: {json.dumps(action_context)}"

        # Store in database as a user message for context
        import uuid
        async with db_manager.async_session() as db:
            from database.models import Message as DBMessage

            db_message = DBMessage(
                conversation_id=interaction.thread_id,
                message_id=f"a2ui_{uuid.uuid4().hex[:12]}",
                role="user",
                content=action_description,
                extra_metadata={
                    "type": "a2ui_interaction",
                    # Store in v0.8 spec format
                    "name": action_name,
                    "context": action_context,
                    "source_component_id": component_id,
                    "surface_id": surface_id,
                    "timestamp": interaction.timestamp,
                }
            )
            db.add(db_message)
            await db.commit()

        return {
            "status": "queued",
            "message": f"Interaction '{interaction.action}' queued for processing",
            "thread_id": interaction.thread_id
        }

    except Exception as e:
        logger.error(f"[A2UI] Error handling interaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)