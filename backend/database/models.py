"""
Database models for conversation persistence
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime (no timezone info).

    This is required because our database uses TIMESTAMP WITHOUT TIME ZONE columns.
    SQLAlchemy/asyncpg cannot mix naive and timezone-aware datetimes.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Integer, DateTime, JSON, Boolean,
    ForeignKey, Index, Float, create_engine, Table, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

Base = declarative_base()

# Association tables for many-to-many relationships
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Index('idx_user_roles', 'user_id', 'role_id')
)

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    Index('idx_role_permissions', 'role_id', 'permission_id')
)


class AIModel(Base):
    """AI Model configuration for orchestrator selection"""
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "claude-haiku-4.5"
    name = Column(String(200), nullable=False)  # e.g., "Claude Haiku 4.5"
    slug = Column(String(200), nullable=False)  # e.g., "claude-haiku-4-5-20251001"
    provider = Column(String(50), nullable=False)  # "anthropic" or "openrouter"
    description = Column(Text, nullable=True)

    # Technical specs
    context_window = Column(Integer, nullable=False)  # e.g., 200000
    max_output = Column(Integer, nullable=False)  # e.g., 64000

    # Pricing (stored as strings for display)
    cost_input = Column(String(50), nullable=True)  # e.g., "$1/1M tokens"
    cost_output = Column(String(50), nullable=True)  # e.g., "$5/1M tokens"

    # Capabilities
    supports_thinking = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)  # Vision/multimodal image processing
    speed = Column(String(20), nullable=True)  # "fast", "medium", "slow"
    intelligence = Column(String(20), nullable=True)  # "high", "very-high", "frontier"

    # Metadata
    recommended_for = Column(JSON, nullable=True)  # Array of use cases
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Permission(Base):
    """Permission model for granular access control"""
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "chat.access"
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # e.g., "chat", "cms", "admin"

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class Role(Base):
    """Role model for grouping permissions"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "Employee", "CMS Editor"
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False)  # System roles cannot be deleted

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    """User model for authentication and analytics"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    bio = Column(String)
    password_hash = Column(String)
    is_whitelisted = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    # Google Workspace OAuth tokens
    google_id = Column(String, unique=True)
    profile_picture = Column(String)
    google_access_token = Column(Text)
    google_refresh_token = Column(Text)
    google_token_expiry = Column(DateTime)

    # GA4 Analytics configuration
    ga4_property_id = Column(String(255), default="325181275")
    ga4_enabled = Column(Boolean, default=True)

    # Google Ads configuration
    google_ads_customer_id = Column(String(255))
    google_ads_enabled = Column(Boolean, default=False)

    # Model preferences
    preferred_model = Column(String(50), default="claude-haiku-4.5")  # Orchestrator model preference

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")


class Conversation(Base):
    """Store conversation threads"""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)  # thread_id
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)  # Auto-generated from first message
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Metadata
    agent_used = Column(String, nullable=True)  # Primary agent used
    tags = Column(JSON, default=list)  # User or auto-generated tags
    is_archived = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)

    # Summary for search
    summary = Column(Text, nullable=True)  # AI-generated summary

    # Fork tracking
    forked_from_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)  # Parent conversation if this is a fork
    fork_summary = Column(Text, nullable=True)  # Comprehensive summary of parent conversation

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    # Note: Memories are NOT cascade deleted - they persist even when conversation is deleted
    # The conversation_id will be set to NULL (ON DELETE SET NULL in database)
    memories = relationship("Memory", back_populates="conversation")

    # Indexes for common queries
    __table_args__ = (
        Index('idx_user_updated', 'user_id', 'updated_at'),
        Index('idx_user_starred', 'user_id', 'is_starred'),
    )


class Message(Base):
    """Store individual messages in conversations"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(String, nullable=False, unique=True)  # Unique message ID from frontend

    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utc_now, nullable=False)

    # Optional metadata
    attachments = Column(JSON, default=list)  # File/image attachments
    tool_calls = Column(JSON, default=list)  # Tool calls made
    reasoning = Column(Text, nullable=True)  # Extended thinking/reasoning from models
    timeline = Column(JSON, default=list)  # Temporal order of events (text, reasoning, tool_calls)
    extra_metadata = Column(JSON, default=dict)  # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)

    # Token counts for analytics
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    # Edit tracking
    edited_at = Column(DateTime, nullable=True)  # Timestamp when message was last edited

    # Relationship
    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index('idx_conv_timestamp', 'conversation_id', 'timestamp'),
    )


class Run(Base):
    """Store background agent runs that persist after client disconnection"""
    __tablename__ = "runs"

    id = Column(String, primary_key=True)  # UUID as string
    thread_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    user_message = Column(Text, nullable=False)

    # Run status lifecycle
    status = Column(String, nullable=False, default="pending")  # pending, in_progress, completed, failed, cancelled
    created_at = Column(DateTime, default=utc_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Results and error handling
    result = Column(JSON, nullable=True)  # {text, tool_calls, reasoning, todos}
    error = Column(Text, nullable=True)
    run_metadata = Column(JSON, default=dict)  # {model, tokens, duration_ms, etc.} - renamed from 'metadata' to avoid SQLAlchemy conflict

    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_runs_thread_id', 'thread_id'),
        Index('idx_runs_user_id', 'user_id'),
        Index('idx_runs_status', 'status'),
        Index('idx_runs_created_at', 'created_at'),
        Index('idx_runs_user_status', 'user_id', 'status'),
    )


class Memory(Base):
    """Store extracted memories and facts from conversations"""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)  # Allow manual memories without conversation
    user_id = Column(String, nullable=False, index=True)

    # Memory content
    fact = Column(Text, nullable=False)  # The extracted fact/memory
    category = Column(String, nullable=True)  # Category: preference, fact, instruction
    confidence = Column(Float, default=1.0)  # Confidence score

    # Vector embedding for semantic search
    embedding = Column(JSON, nullable=True)  # Store as JSON array

    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_accessed = Column(DateTime, default=utc_now, nullable=False)
    access_count = Column(Integer, default=0)

    # Relationship
    conversation = relationship("Conversation", back_populates="memories")

    __table_args__ = (
        Index('idx_user_category', 'user_id', 'category'),
        Index('idx_user_accessed', 'user_id', 'last_accessed'),
    )


class DocChunk(Base):
    """Store documentation chunks with embeddings for semantic search.

    This is derived data from the 'docs' table - chunks are regenerated when docs change.
    Used by search_docs() tool for semantic similarity search.
    """
    __tablename__ = "doc_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False, index=True)  # Relative path: "graphql-operations/products/search.md"
    chunk_index = Column(Integer, nullable=False)  # Position in file (0, 1, 2...)

    # Content
    chunk_text = Column(Text, nullable=False)  # Actual content
    chunk_tokens = Column(Integer, nullable=True)  # Token count for this chunk
    heading_context = Column(Text, nullable=True)  # Parent heading hierarchy (e.g., "## Products / ### Search")

    # Vector embedding for semantic search
    embedding = Column(JSON, nullable=True)  # 3072-dim vector stored as JSON array

    # Metadata
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Indexes (renamed from idx_file_* to idx_doc_chunks_*)
    __table_args__ = (
        Index('idx_doc_chunks_file_path', 'file_path'),
        Index('idx_doc_chunks_file_chunk', 'file_path', 'chunk_index', unique=True),
    )


class UserPreference(Base):
    """Store user preferences and settings"""
    __tablename__ = "user_preferences"

    user_id = Column(String, primary_key=True)
    preferences = Column(JSON, default=dict)  # General preferences

    # UI preferences
    theme = Column(String, default="light")
    sidebar_collapsed = Column(Boolean, default=False)

    # Agent preferences
    default_model = Column(String, nullable=True)
    temperature = Column(Float, default=0.7)

    # Human-in-the-loop preferences
    hitl_enabled = Column(Boolean, default=True)  # Enable approval mode for tool executions (default: TRUE for safety)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class UserMCPServer(Base):
    """Store user-specific MCP server configurations"""
    __tablename__ = "user_mcp_servers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Server identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Transport configuration
    transport_type = Column(String(50), nullable=False)  # stdio, sse, http
    config = Column(JSON, nullable=False)  # Flexible config for each transport type

    # Authentication configuration
    auth_type = Column(String(20), default="none", nullable=False)  # none, api_key, oauth
    oauth_config = Column(JSON, nullable=True)  # {authorization_url, token_url, client_id, scopes}

    # Status
    enabled = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    oauth_token = relationship("UserMCPOAuthToken", back_populates="mcp_server", uselist=False, cascade="all, delete-orphan")

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_user_server_name'),
        Index('idx_user_mcp_servers_user_id', 'user_id'),
        Index('idx_user_mcp_servers_enabled', 'enabled'),
    )


class UserMCPOAuthToken(Base):
    """Store OAuth tokens for remote MCP servers requiring authentication"""
    __tablename__ = "user_mcp_oauth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mcp_server_id = Column(Integer, ForeignKey("user_mcp_servers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Token storage (encrypted at application level)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer")

    # Token metadata
    expires_at = Column(DateTime, nullable=True)
    scopes = Column(JSON, nullable=True)  # Array of scope strings

    # OAuth state for PKCE flow (temporary, cleared after completion)
    pkce_code_verifier = Column(Text, nullable=True)
    oauth_state = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    mcp_server = relationship("UserMCPServer", back_populates="oauth_token")

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'mcp_server_id', name='unique_user_mcp_oauth'),
        Index('idx_mcp_oauth_expires', 'expires_at'),
    )


# Database connection utilities
class DatabaseManager:
    """Manage database connections and operations"""

    def __init__(self, database_url: str):
        """Initialize database manager with optimized connection pool settings"""
        # Convert postgresql:// to postgresql+asyncpg:// for async
        if database_url.startswith("postgresql://"):
            async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
            # Remove sslmode query parameter (not supported by asyncpg)
            if "?sslmode=" in async_url:
                async_url = async_url.split("?sslmode=")[0]
        else:
            async_url = database_url

        # Configure SSL and timeouts for remote connections
        connect_args = {}
        if "akamaidb.net" in async_url or "supabase.co" in async_url:
            # For asyncpg via SQLAlchemy, timeouts must be in connect_args
            # Using 30s timeout for WSL environments with high latency (280-900ms RTT)
            connect_args = {
                "ssl": "require",
                "timeout": 30,  # Connection timeout in seconds (asyncpg parameter)
                "command_timeout": 30,  # Command execution timeout
                "server_settings": {
                    "application_name": "espressobot_dev"
                }
            }

        # Create async engine with optimized pool settings
        self.engine = create_async_engine(
            async_url,
            echo=False,
            connect_args=connect_args,
            # Connection pool settings
            pool_size=10,  # Maintain 10 persistent connections (up from 5)
            max_overflow=20,  # Allow 20 additional overflow connections (up from 10)
            pool_timeout=30,  # Wait 30 seconds for connection availability
            pool_recycle=1800,  # Recycle connections after 30 minutes (prevents stale connections)
            pool_pre_ping=True,  # Verify connection health before using (prevents errors)
            # Graceful shutdown settings
            pool_reset_on_return='rollback',  # Reset connection state on return to pool
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def create_tables(self):
        """Create all tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        """Get async database session"""
        async with self.async_session() as session:
            yield session

    async def close(self):
        """Close database connections gracefully"""
        import asyncio
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Dispose engine with timeout to prevent hanging
            # Use asyncio.wait_for to timeout if disposal takes too long
            await asyncio.wait_for(self.engine.dispose(), timeout=5.0)
            logger.info("Database connections closed successfully")
        except asyncio.TimeoutError:
            logger.warning("Database disposal timed out after 5 seconds")
        except asyncio.CancelledError:
            # Suppress cancellation errors during shutdown - this is expected
            logger.debug("Database disposal cancelled (expected during shutdown)")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
            # Don't raise - we're shutting down anyway

class DailyAnalyticsCache(Base):
    """Cache daily analytics data from multiple sources"""
    
    __tablename__ = "daily_analytics_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, unique=True, index=True)
    
    # Shopify data
    shopify_revenue = Column(Float)
    shopify_orders = Column(Integer)
    shopify_aov = Column(Float)
    shopify_top_products = Column(JSON)
    shopify_raw_data = Column(JSON)
    
    # GA4 data
    ga4_revenue = Column(Float)
    ga4_transactions = Column(Integer)
    ga4_users = Column(Integer)
    ga4_conversion_rate = Column(Float)
    ga4_traffic_sources = Column(JSON)
    ga4_ads_performance = Column(JSON)
    ga4_raw_data = Column(JSON)
    
    # Google Workspace data
    workspace_data = Column(JSON, nullable=True)
    
    # Metadata
    is_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class HourlyAnalyticsCache(Base):
    """Cache hourly analytics for today's data"""
    
    __tablename__ = "hourly_analytics_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False, index=True)
    hour = Column(Integer, nullable=False)
    
    # Hourly metrics
    revenue = Column(Float)
    orders = Column(Integer)
    
    # Metadata
    created_at = Column(DateTime, default=utc_now)


class AnalyticsSyncStatus(Base):
    """Track sync status for bulk data fetching"""

    __tablename__ = "analytics_sync_status"

    id = Column(Integer, primary_key=True, index=True)
    sync_type = Column(String(50), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Status tracking
    status = Column(String(20), default='pending')
    total_days = Column(Integer)
    processed_days = Column(Integer, default=0)
    failed_days = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)


class Note(Base):
    """User notes for personal knowledge management (Second Brain)"""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(String, nullable=False, index=True)

    # Core content
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    # Organization
    category = Column(String, default="personal")
    tags = Column(JSON, default=list)
    is_starred = Column(Boolean, default=False)

    # Semantic search (pgvector halfvec for 3072-dim embeddings)
    embedding_halfvec = Column(Text, nullable=True)  # Stored as text, handled by pgvector

    # Obsidian sync support
    obsidian_vault_id = Column(String, nullable=True)
    obsidian_file_path = Column(Text, nullable=True)
    obsidian_content_hash = Column(String, nullable=True)
    obsidian_last_synced = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    last_accessed = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    conversation = relationship("Conversation", foreign_keys=[conversation_id])
    published_note = relationship("PublishedNote", back_populates="note", uselist=False, cascade="all, delete-orphan")

    # Indexes handled by migration file


class PublishedNote(Base):
    """Publicly accessible notes with optional security"""
    __tablename__ = "published_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(String, nullable=False, index=True)

    # Public access
    public_id = Column(String(32), unique=True, nullable=False, index=True)  # Random URL-safe identifier

    # Security options
    password_hash = Column(String, nullable=True)  # Optional bcrypt password protection
    expires_at = Column(DateTime, nullable=True)  # Optional expiration date

    # Metadata
    view_count = Column(Integer, default=0)
    last_viewed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    note = relationship("Note", back_populates="published_note")

    # Indexes handled by migration file


class BFCMAnalyticsCache(Base):
    """Cache BFCM analytics data with multi-year support"""
    __tablename__ = "bfcm_analytics_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    hour = Column(Integer, nullable=True)  # 0-23, NULL for daily aggregates

    # Revenue metrics
    revenue = Column(Float, nullable=True)
    order_count = Column(Integer, nullable=True)
    aov = Column(Float, nullable=True)

    # Top products (JSON array)
    top_products = Column(JSON, nullable=True)

    # Category breakdown (JSON object)
    category_breakdown = Column(JSON, nullable=True)

    # GA4 metrics (optional)
    ga4_users = Column(Integer, nullable=True)
    ga4_sessions = Column(Integer, nullable=True)
    ga4_conversion_rate = Column(Float, nullable=True)

    # Metadata
    is_live = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index('idx_bfcm_cache_year_date', 'year', 'date'),
        UniqueConstraint('year', 'date', 'hour', name='unique_bfcm_year_date_hour'),
    )


class BFCMMilestone(Base):
    """Track BFCM revenue milestones for celebration alerts"""
    __tablename__ = "bfcm_milestones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    threshold = Column(Float, nullable=False)  # Revenue threshold (e.g., 50000, 100000)
    achieved = Column(Boolean, default=False)
    achieved_at = Column(DateTime, nullable=True)
    notified = Column(Boolean, default=False)  # Has toast been shown?

    __table_args__ = (
        UniqueConstraint('year', 'threshold', name='unique_bfcm_milestone'),
    )


class BoxingWeekAnalyticsCache(Base):
    """Cache Boxing Week analytics data with multi-year support"""
    __tablename__ = "boxing_week_analytics_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    hour = Column(Integer, nullable=True)  # 0-23, NULL for daily aggregates

    # Revenue metrics
    revenue = Column(Float, nullable=True)
    order_count = Column(Integer, nullable=True)
    aov = Column(Float, nullable=True)

    # Top products (JSON array)
    top_products = Column(JSON, nullable=True)

    # Category breakdown (JSON object)
    category_breakdown = Column(JSON, nullable=True)

    # GA4 metrics (optional)
    ga4_users = Column(Integer, nullable=True)
    ga4_sessions = Column(Integer, nullable=True)
    ga4_conversion_rate = Column(Float, nullable=True)

    # Metadata
    is_live = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index('idx_bw_cache_year_date', 'year', 'date'),
        UniqueConstraint('year', 'date', 'hour', name='unique_bw_year_date_hour'),
    )


class BoxingWeekMilestone(Base):
    """Track Boxing Week revenue milestones for celebration alerts"""
    __tablename__ = "boxing_week_milestones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    threshold = Column(Float, nullable=False)  # Revenue threshold (e.g., 50000, 100000)
    achieved = Column(Boolean, default=False)
    achieved_at = Column(DateTime, nullable=True)
    notified = Column(Boolean, default=False)  # Has toast been shown?

    __table_args__ = (
        UniqueConstraint('year', 'threshold', name='unique_bw_milestone'),
    )


class WorkflowConfig(Base):
    """Workflow configuration per user - stores automation settings"""
    __tablename__ = "workflow_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False)  # 'email_autolabel', 'daily_sales_report', etc.

    # Status
    enabled = Column(Boolean, default=False)

    # Schedule settings
    frequency = Column(String(20), default='daily')  # 'hourly', '6hours', 'daily', 'weekly', 'manual'
    cron_expression = Column(String(100), nullable=True)  # For custom schedules

    # Workflow-specific config (JSON)
    config = Column(JSON, default=dict)
    # Examples:
    # email_autolabel: {"email_count": 50, "skip_labeled": true, "max_age_days": 7}
    # daily_sales_report: {"format": "markdown", "send_email": true}

    # Tracking
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user = relationship("User", backref="workflow_configs")
    runs = relationship("WorkflowRun", back_populates="workflow_config", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'workflow_type', name='unique_user_workflow'),
        Index('idx_workflow_configs_enabled', 'enabled'),
        Index('idx_workflow_configs_next_run', 'next_run_at'),
    )


class WorkflowRun(Base):
    """Workflow execution history - tracks each run of a workflow"""
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_config_id = Column(Integer, ForeignKey("workflow_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False)  # Denormalized for easy querying

    # Execution details
    status = Column(String(20), nullable=False, default='pending')  # 'pending', 'running', 'completed', 'failed'
    trigger_type = Column(String(20), nullable=False)  # 'manual', 'scheduled'

    # Timing
    started_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)  # Execution time in milliseconds

    # Results (JSON)
    result = Column(JSON, nullable=True)
    # Examples:
    # email_autolabel: {"emails_processed": 50, "labels_applied": {"To Respond": 5, "FYI": 20}, "skipped": 3}
    # daily_sales_report: {"total_sales": "$5,234.00", "orders": 42, "report_url": "..."}

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    workflow_config = relationship("WorkflowConfig", back_populates="runs")
    user = relationship("User")

    __table_args__ = (
        Index('idx_workflow_runs_started', 'started_at'),
        Index('idx_workflow_runs_status', 'status'),
    )


class WorkflowDefinition(Base):
    """User-created prompt-based workflow definitions"""
    __tablename__ = "workflow_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Identity
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(10), default='🤖')  # Emoji for display

    # The prompt to execute (sent to orchestrator)
    prompt = Column(Text, nullable=False)

    # Optional: hint for which agent to use (NULL = orchestrator decides)
    agent_hint = Column(String(50), nullable=True)  # 'google_workspace', 'web_search', etc.

    # Schedule settings
    enabled = Column(Boolean, default=False)
    frequency = Column(String(20), default='daily')  # 'hourly', '6hours', 'daily', 'weekly', 'once', 'manual'
    cron_expression = Column(String(100), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)  # For one-time runs (frequency='once')

    # Execution settings
    timeout_seconds = Column(Integer, default=120)
    notify_on_complete = Column(Boolean, default=True)  # Default to true
    notify_on_failure = Column(Boolean, default=True)

    # Tracking
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user = relationship("User", backref="workflow_definitions")

    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_user_workflow_name'),
        Index('idx_workflow_defs_enabled', 'enabled'),
        Index('idx_workflow_defs_next_run', 'next_run_at'),
    )


class InventoryAlert(Base):
    """Inventory alerts for stockout risks and forecasting notifications"""
    __tablename__ = "inventory_alerts"

    id = Column(String, primary_key=True)  # UUID as string
    sku = Column(String(255), nullable=False, index=True)
    warehouse_id = Column(String(255), nullable=True)  # NULL means all warehouses
    forecast_id = Column(String(255), nullable=True)  # Reference to inventory_forecasts

    # Alert type and severity
    alert_type = Column(String(50), nullable=False)  # stockout_risk, overstock_warning, accuracy_drift, demand_spike
    severity = Column(String(20), default='medium')  # low, medium, high, critical

    # Content
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=True)

    # Metadata
    days_until_stockout = Column(Integer, nullable=True)
    days_of_overstock = Column(Integer, nullable=True)
    current_quantity = Column(Integer, nullable=True)
    predicted_quantity = Column(Integer, nullable=True)

    # Status
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index('idx_alerts_unack', 'is_acknowledged', 'severity', 'created_at'),
        Index('idx_alerts_sku', 'sku', 'created_at'),
        Index('idx_alerts_type', 'alert_type', 'created_at'),
    )


class SkuVaultSalesCache(Base):
    """Cached daily sales data from SkuVault for Prophet forecasting"""
    __tablename__ = "skuvault_sales_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifiers
    sku = Column(String(255), nullable=False, index=True)
    sale_date = Column(DateTime, nullable=False)
    warehouse_id = Column(String(255), nullable=True)  # NULL = aggregate

    # Sales data
    units_sold = Column(Integer, nullable=False, default=0)
    revenue = Column(Float, nullable=False, default=0)
    order_count = Column(Integer, nullable=False, default=0)

    # Metadata
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('sku', 'sale_date', 'warehouse_id', name='unique_sku_date_warehouse'),
        Index('idx_sales_cache_sku_date', 'sku', 'sale_date'),
        Index('idx_sales_cache_date', 'sale_date'),
    )


class SkuVaultSyncStatus(Base):
    """Tracks sync status for SkuVault data caching"""
    __tablename__ = "skuvault_sync_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String(50), nullable=False, unique=True)  # 'sales', 'inventory', 'products'

    # Date range synced
    last_sync_date = Column(DateTime, nullable=True)  # Last date we have data for
    oldest_sync_date = Column(DateTime, nullable=True)  # Earliest date we have data for

    # Status
    status = Column(String(20), default='idle')  # idle, running, completed, failed
    last_run_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    # Stats
    total_records = Column(Integer, default=0)
    records_synced_last_run = Column(Integer, default=0)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class SkuVaultInventoryCache(Base):
    """Cached inventory levels from SkuVault - updated daily via sync"""
    __tablename__ = "skuvault_inventory_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identifiers
    sku = Column(String(255), nullable=False, index=True)
    warehouse_id = Column(String(255), nullable=True)  # NULL = aggregate total
    warehouse_name = Column(String(255), nullable=True)

    # Inventory levels
    quantity_on_hand = Column(Integer, nullable=False, default=0)
    quantity_available = Column(Integer, nullable=False, default=0)
    quantity_committed = Column(Integer, nullable=False, default=0)

    # Metadata
    snapshot_date = Column(DateTime, nullable=False)  # When this snapshot was taken
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('sku', 'warehouse_id', name='unique_sku_warehouse_inventory'),
        Index('idx_inventory_cache_sku', 'sku'),
    )
