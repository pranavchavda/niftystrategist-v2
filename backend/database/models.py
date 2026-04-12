"""
Database models for Nifty Strategist v2 - AI Trading Agent

Core infrastructure from EspressoBot, stripped of e-commerce, with trading-specific models.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Integer, DateTime, JSON, Boolean,
    ForeignKey, Index, Float, Table, UniqueConstraint, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import enum


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime (no timezone info).

    Required because database uses TIMESTAMP WITHOUT TIME ZONE columns.
    SQLAlchemy/asyncpg cannot mix naive and timezone-aware datetimes.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


Base = declarative_base()

# ==============================================================================
# Association tables for many-to-many relationships
# ==============================================================================

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


# ==============================================================================
# Core Infrastructure Models (from EspressoBot)
# ==============================================================================

class AIModel(Base):
    """AI Model configuration for orchestrator selection"""
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "deepseek-chat"
    name = Column(String(200), nullable=False)  # e.g., "DeepSeek Chat"
    slug = Column(String(200), nullable=False)  # e.g., "deepseek/deepseek-chat"
    provider = Column(String(50), nullable=False)  # "openrouter", "anthropic"
    description = Column(Text, nullable=True)

    # Technical specs
    context_window = Column(Integer, nullable=False)  # e.g., 64000
    max_output = Column(Integer, nullable=False)  # e.g., 8000

    # Pricing (stored as strings for display)
    cost_input = Column(String(50), nullable=True)  # e.g., "$0.14/1M tokens"
    cost_output = Column(String(50), nullable=True)  # e.g., "$0.28/1M tokens"

    # Capabilities
    supports_thinking = Column(Boolean, default=False)
    thinking_effort = Column(String(20), nullable=True)  # 'high', 'medium', 'low', or None
    supports_vision = Column(Boolean, default=False)
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
    category = Column(String(50), nullable=True)  # e.g., "chat", "trading", "admin"

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class Role(Base):
    """Role model for grouping permissions"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "Trader", "Admin"
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False)  # System roles cannot be deleted

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    """User model for authentication - simplified for trading app"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    # Upstox OAuth tokens (encrypted at application level)
    upstox_access_token = Column(Text, nullable=True)
    upstox_refresh_token = Column(Text, nullable=True)
    upstox_token_expiry = Column(DateTime, nullable=True)
    upstox_user_id = Column(String(100), nullable=True)  # Upstox user identifier

    # Per-user Upstox API credentials (encrypted, for multi-user support)
    upstox_api_key = Column(Text, nullable=True)
    upstox_api_secret = Column(Text, nullable=True)

    # TOTP auto-login credentials (encrypted, for automatic token refresh)
    upstox_mobile = Column(Text, nullable=True)
    upstox_pin = Column(Text, nullable=True)
    upstox_totp_secret = Column(Text, nullable=True)
    upstox_totp_last_failed_at = Column(DateTime, nullable=True)

    # Password reset
    password_reset_token = Column(String(128), nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)

    # Trading mode: 'paper' or 'live'
    trading_mode = Column(String(10), default="live", nullable=False)

    # Model preferences
    preferred_model = Column(String(100), default="deepseek/deepseek-chat")

    # Per-user order node URL for SEBI static IP compliance
    # e.g., "http://localhost:8001" or "http://<nanode-ip>:8001"
    order_node_url = Column(String(255), nullable=True)

    # Standing trading mandate for autonomous awakenings (JSONB)
    # {risk_per_trade, daily_loss_cap, allowed_instruments, cutoff_time, auto_squareoff_time, approved_at}
    trading_mandate = Column(JSON, nullable=True)

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    watchlist_items = relationship("WatchlistItem", back_populates="user", cascade="all, delete-orphan")


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
    forked_from_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    fork_summary = Column(Text, nullable=True)  # Comprehensive summary of parent conversation

    # Daily thread tracking (recurring awakenings)
    is_daily_thread = Column(Boolean, default=False)
    daily_thread_date = Column(DateTime, nullable=True)  # DATE column — store as date, not string

    # Compaction tracking
    last_compacted_at = Column(DateTime, nullable=True)  # When thread was last compacted

    # Thread embedding tracking (cross-thread awareness)
    needs_processing_since = Column(DateTime, nullable=True)  # Set on message save, cleared after embedding
    last_embedded_at = Column(DateTime, nullable=True)  # When thread turns were last embedded

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="conversation")

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
    reasoning = Column(Text, nullable=True)  # Extended thinking/reasoning
    timeline = Column(JSON, default=list)  # Temporal order of events
    extra_metadata = Column(JSON, default=dict)

    # Token counts for analytics
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    # Edit tracking
    edited_at = Column(DateTime, nullable=True)

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
    run_metadata = Column(JSON, default=dict)  # {model, tokens, duration_ms, etc.}

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
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(String, nullable=False, index=True)

    # Memory content
    fact = Column(Text, nullable=False)  # The extracted fact/memory
    category = Column(String, nullable=True)  # Trading-focused categories (see CLAUDE.md)
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
    """Store documentation chunks with embeddings for semantic search"""
    __tablename__ = "doc_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)

    # Content
    chunk_text = Column(Text, nullable=False)
    chunk_tokens = Column(Integer, nullable=True)
    heading_context = Column(Text, nullable=True)

    # Vector embedding for semantic search
    embedding = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index('idx_doc_chunks_file_path', 'file_path'),
        Index('idx_doc_chunks_file_chunk', 'file_path', 'chunk_index', unique=True),
    )


class UserPreference(Base):
    """Store user preferences and settings"""
    __tablename__ = "user_preferences"

    user_id = Column(String, primary_key=True)
    preferences = Column(JSON, default=dict)

    # UI preferences
    theme = Column(String, default="light")
    sidebar_collapsed = Column(Boolean, default=False)

    # Agent preferences
    default_model = Column(String, nullable=True)
    temperature = Column(Float, default=0.7)

    # Human-in-the-loop preferences (always enabled for trading)
    hitl_enabled = Column(Boolean, default=True)

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
    config = Column(JSON, nullable=False)

    # Authentication configuration
    auth_type = Column(String(20), default="none", nullable=False)  # none, api_key, oauth
    oauth_config = Column(JSON, nullable=True)

    # Status
    enabled = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    oauth_token = relationship("UserMCPOAuthToken", back_populates="mcp_server", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_user_server_name'),
        Index('idx_user_mcp_servers_user_id', 'user_id'),
        Index('idx_user_mcp_servers_enabled', 'enabled'),
    )


class UserMCPOAuthToken(Base):
    """Store OAuth tokens for remote MCP servers"""
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
    scopes = Column(JSON, nullable=True)

    # OAuth state for PKCE flow
    pkce_code_verifier = Column(Text, nullable=True)
    oauth_state = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    mcp_server = relationship("UserMCPServer", back_populates="oauth_token")

    __table_args__ = (
        UniqueConstraint('user_id', 'mcp_server_id', name='unique_user_mcp_oauth'),
        Index('idx_mcp_oauth_expires', 'expires_at'),
    )


class Note(Base):
    """User notes for personal knowledge management"""
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

    # Semantic search
    embedding_halfvec = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    last_accessed = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    conversation = relationship("Conversation", foreign_keys=[conversation_id])
    published_note = relationship("PublishedNote", back_populates="note", uselist=False, cascade="all, delete-orphan")


class PublishedNote(Base):
    """Publicly accessible notes with optional security"""
    __tablename__ = "published_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(String, nullable=False, index=True)

    public_id = Column(String(32), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    view_count = Column(Integer, default=0)
    last_viewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    note = relationship("Note", back_populates="published_note")


# ==============================================================================
# Trading-Specific Models
# ==============================================================================

class TradeStatus(enum.Enum):
    """Trade execution status"""
    PROPOSED = "proposed"       # Agent proposed, awaiting approval
    APPROVED = "approved"       # User approved, pending execution
    EXECUTING = "executing"     # Order placed, awaiting fill
    COMPLETED = "completed"     # Order filled
    REJECTED = "rejected"       # User rejected proposal
    CANCELLED = "cancelled"     # Order cancelled
    FAILED = "failed"           # Execution failed


class TradeDirection(enum.Enum):
    """Trade direction"""
    BUY = "BUY"
    SELL = "SELL"


class Trade(Base):
    """Record of all trades (proposed, executed, rejected)"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)

    # Trade identification
    symbol = Column(String(50), nullable=False, index=True)  # e.g., "RELIANCE", "TCS"
    exchange = Column(String(10), nullable=False, default="NSE")  # NSE, BSE
    instrument_token = Column(String(50), nullable=True)  # Upstox instrument token

    # Trade details
    direction = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Integer, nullable=False)
    order_type = Column(String(20), default="MARKET")  # MARKET, LIMIT, SL, SL-M

    # Pricing
    proposed_price = Column(Float, nullable=True)  # Price when proposed
    limit_price = Column(Float, nullable=True)  # For limit orders
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    executed_price = Column(Float, nullable=True)  # Actual fill price

    # Risk metrics (calculated at proposal time)
    risk_reward_ratio = Column(Float, nullable=True)
    amount_at_risk = Column(Float, nullable=True)  # Max loss in rupees
    position_size_pct = Column(Float, nullable=True)  # % of portfolio

    # Status tracking
    status = Column(String(20), nullable=False, default="proposed")
    upstox_order_id = Column(String(100), nullable=True)  # Upstox order reference

    # Agent reasoning
    reasoning = Column(Text, nullable=True)  # Why the trade was proposed
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Timestamps
    proposed_at = Column(DateTime, default=utc_now, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Result (for completed trades)
    pnl = Column(Float, nullable=True)  # Profit/loss in rupees
    pnl_percentage = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="trades")
    agent_decisions = relationship("AgentDecision", back_populates="trade", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_trades_user_status', 'user_id', 'status'),
        Index('idx_trades_symbol', 'symbol', 'proposed_at'),
        Index('idx_trades_proposed_at', 'proposed_at'),
    )


class AgentDecision(Base):
    """Audit trail for agent analysis and decisions"""
    __tablename__ = "agent_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id", ondelete="CASCADE"), nullable=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)

    # Decision context
    decision_type = Column(String(50), nullable=False)  # market_analysis, trade_proposal, risk_assessment
    symbol = Column(String(50), nullable=True, index=True)

    # Analysis data (JSON for flexibility)
    input_data = Column(JSON, nullable=True)  # What the agent saw
    analysis = Column(JSON, nullable=True)  # Technical indicators, patterns, etc.
    output = Column(JSON, nullable=True)  # Decision/recommendation

    # Confidence and reasoning
    confidence_score = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)  # Human-readable explanation

    # Model info
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    trade = relationship("Trade", back_populates="agent_decisions")

    __table_args__ = (
        Index('idx_agent_decisions_user', 'user_id', 'created_at'),
        Index('idx_agent_decisions_type', 'decision_type', 'created_at'),
    )


class WatchlistItem(Base):
    """User's watchlist for tracking stocks"""
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Stock identification
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(10), nullable=False, default="NSE")
    instrument_token = Column(String(50), nullable=True)
    company_name = Column(String(255), nullable=True)

    # Organization
    watchlist_name = Column(String(100), default="Default")  # Support multiple watchlists
    sort_order = Column(Integer, default=0)

    # User notes
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=list)

    # Alerts (optional)
    alert_above = Column(Float, nullable=True)  # Alert if price goes above
    alert_below = Column(Float, nullable=True)  # Alert if price goes below

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="watchlist_items")

    __table_args__ = (
        UniqueConstraint('user_id', 'symbol', 'exchange', 'watchlist_name', name='unique_watchlist_item'),
        Index('idx_watchlist_user', 'user_id', 'watchlist_name'),
    )


class PriceForecast(Base):
    """TimesFM ML price forecasts for watchlist symbols."""
    __tablename__ = "price_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(10), nullable=False, default="NSE")
    horizon_days = Column(Integer, nullable=False)
    current_price = Column(Float, nullable=False)
    data_points_used = Column(Integer, nullable=False)
    signal = Column(String(10), nullable=False)  # bullish, bearish, neutral
    confidence = Column(Float, nullable=False)
    predicted_change_pct = Column(Float, nullable=False)
    predictions = Column(JSON, nullable=False)  # [{date, price, lower, upper}, ...]
    model_version = Column(String(100), nullable=False, default="google/timesfm-2.5-200m-pytorch")
    inference_time_ms = Column(Integer, nullable=True)
    actual_prices = Column(JSON, nullable=True)  # filled later for accuracy tracking
    mape = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index('idx_forecasts_user_symbol', 'user_id', 'symbol', 'created_at'),
        Index('idx_forecasts_user_latest', 'user_id', 'created_at'),
    )


class MonitorRule(Base):
    """IFTTT-style trade monitoring rules evaluated by nf-monitor daemon."""
    __tablename__ = "monitor_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    trigger_type = Column(String(20), nullable=False)
    trigger_config = Column(JSON, nullable=False)

    action_type = Column(String(20), nullable=False)
    action_config = Column(JSON, nullable=False)

    instrument_token = Column(String(50), nullable=True)
    symbol = Column(String(50), nullable=True, index=True)
    linked_trade_id = Column(Integer, ForeignKey("trades.id", ondelete="SET NULL"), nullable=True)
    linked_order_id = Column(String(100), nullable=True)

    fire_count = Column(Integer, default=0, nullable=False)
    max_fires = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    fired_at = Column(DateTime, nullable=True)

    # Strategy grouping (set by nf-strategy deploy)
    group_id = Column(String(50), nullable=True)
    strategy_name = Column(String(50), nullable=True)
    role = Column(String(50), nullable=True)  # e.g. "entry_long", "sl_long", "trailing_short"

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index('idx_monitor_rules_user_enabled', 'user_id', 'enabled'),
        Index('idx_monitor_rules_instrument', 'instrument_token'),
    )


class MonitorLog(Base):
    """Audit log for monitor rule firings."""
    __tablename__ = "monitor_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("monitor_rules.id", ondelete="SET NULL"), nullable=True)

    trigger_snapshot = Column(JSON, nullable=True)
    action_taken = Column(String(50), nullable=False)
    action_result = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    rule = relationship("MonitorRule")

    __table_args__ = (
        Index('idx_monitor_logs_user', 'user_id', 'created_at'),
        Index('idx_monitor_logs_rule', 'rule_id', 'created_at'),
    )


# ==============================================================================
# Workflow Automation Models
# ==============================================================================

class WorkflowConfig(Base):
    """Built-in workflow configuration per user"""
    __tablename__ = "workflow_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False)

    enabled = Column(Boolean, default=False)
    frequency = Column(String(20), default="daily")
    cron_expression = Column(String(100), nullable=True)

    config = Column(JSON, default=dict)

    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'workflow_type', name='unique_workflow_config'),
    )


class WorkflowRun(Base):
    """Workflow execution history"""
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_config_id = Column(Integer, ForeignKey("workflow_configs.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_type = Column(String(50), nullable=False)

    status = Column(String(20), nullable=False, default="pending")
    trigger_type = Column(String(20), nullable=False)

    started_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index('idx_workflow_runs_user', 'user_id'),
        Index('idx_workflow_runs_config', 'workflow_config_id'),
        Index('idx_workflow_runs_started', 'started_at'),
    )


class WorkflowDefinition(Base):
    """User-created prompt-based custom workflows"""
    __tablename__ = "workflow_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(10), default="🤖")

    prompt = Column(Text, nullable=False)
    agent_hint = Column(String(50), nullable=True)

    # Thread-bound follow-ups (NULL for regular automations)
    thread_id = Column(String, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)

    enabled = Column(Boolean, default=False)
    frequency = Column(String(20), default="daily")
    cron_expression = Column(String(100), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)

    timeout_seconds = Column(Integer, default=900)
    notify_on_complete = Column(Boolean, default=False)
    notify_on_failure = Column(Boolean, default=True)

    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_workflow_definition'),
        Index('idx_workflow_defs_user', 'user_id'),
        Index('idx_workflow_defs_enabled', 'enabled'),
        Index('idx_workflow_defs_thread_id', 'thread_id'),
    )


class WorkflowActionLog(Base):
    """Log of tool calls and actions executed during workflow runs.

    Purpose: Track exactly what the agent did during scheduled events (awakenings, automations).
    This provides complete audit trail and helps debug autonomous trading decisions.
    """
    __tablename__ = "workflow_action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tool invocation details
    tool_name = Column(String(50), nullable=False, index=True)  # e.g., 'nf-order', 'nf-portfolio', 'nf-analyze'
    tool_args = Column(JSON, nullable=False)  # Command + args, e.g., {"command": "buy ADANIPOWER 487 --product I"}

    # Execution result
    tool_result = Column(JSON, nullable=True)  # Result/output from the tool
    execution_status = Column(String(20), nullable=True, index=True)  # 'success', 'failed', 'pending'
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, default=utc_now, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Metadata for later analysis
    sequence_order = Column(Integer, nullable=False)  # Order within the workflow
    agent_reasoning = Column(Text, nullable=True)  # Why agent called this tool
    market_context = Column(JSON, nullable=True)  # Market state at time of execution

    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index('idx_workflow_action_logs_workflow', 'workflow_run_id'),
        Index('idx_workflow_action_logs_user', 'user_id'),
        Index('idx_workflow_action_logs_tool', 'tool_name'),
    )


class ThreadEmbedding(Base):
    """Embedded conversation turns for cross-thread semantic search.

    Each row is one user+assistant turn pair, embedded via
    pplx-embed-context-v1-0.6b (1024 dims). Max 20 recent threads
    per user, auto-purged by the thread embedder.
    """
    __tablename__ = "thread_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False)
    turn_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    # halfvec(1024) — pgvector half-precision vector
    embedding_halfvec = Column(String, nullable=True)  # Stored as halfvec in DB via raw SQL
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index('idx_thread_emb_user', 'user_id'),
        Index('idx_thread_emb_conv', 'conversation_id'),
        # UniqueConstraint handled by UNIQUE(conversation_id, turn_index) in migration
    )


# ==============================================================================
# Recurring Awakening Models
# ==============================================================================

class UserAwakeningSchedule(Base):
    """Per-user recurring awakening schedule.

    Each row represents a scheduled awakening window (e.g., "Morning Scan" at 9:20 AM IST).
    The scheduler converts IST times to UTC CronTrigger jobs at startup.
    All awakenings for a given day write to a single daily trading thread.
    """
    __tablename__ = "user_awakening_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Schedule identity
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    # Timing (IST — converted to UTC at scheduler load)
    cron_hour = Column(Integer, nullable=False)      # 0-23 IST
    cron_minute = Column(Integer, default=0, nullable=False)  # 0-59
    weekdays_only = Column(Boolean, default=True, nullable=False)

    # Prompt
    prompt = Column(Text, nullable=False)

    # Execution config
    timeout_seconds = Column(Integer, default=600, nullable=False)
    model_override = Column(String(100), nullable=True)

    # Tracking
    last_run_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    run_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_awakening_schedule'),
        Index('idx_awakening_schedules_user', 'user_id'),
        Index('idx_awakening_schedules_enabled', 'enabled'),
    )


# ==============================================================================
# Database Connection Manager
# ==============================================================================

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

        # Configure SSL and timeouts for remote connections (Supabase)
        connect_args = {}
        if "supabase.co" in async_url:
            connect_args = {
                "ssl": "require",
                "timeout": 30,
                "command_timeout": 30,
                "server_settings": {
                    "application_name": "nifty_strategist_v2"
                }
            }

        # Create async engine with optimized pool settings
        self.engine = create_async_engine(
            async_url,
            echo=False,
            connect_args=connect_args,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            pool_reset_on_return='rollback',
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
            await asyncio.wait_for(self.engine.dispose(), timeout=5.0)
            logger.info("Database connections closed successfully")
        except asyncio.TimeoutError:
            logger.warning("Database disposal timed out after 5 seconds")
        except asyncio.CancelledError:
            logger.debug("Database disposal cancelled (expected during shutdown)")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
