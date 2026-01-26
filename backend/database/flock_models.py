"""
Database models for Flock integration
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, DateTime, JSON, Boolean,
    ForeignKey, Index, Float, Enum
)
from sqlalchemy.orm import relationship
from .models import Base
import enum


class FlockChannelType(str, enum.Enum):
    """Type of Flock channel"""
    GROUP = "group"
    CHANNEL = "channel"
    DM = "dm"  # Direct message / 1-on-1


class ActionableType(str, enum.Enum):
    """Type of actionable item extracted from messages"""
    TASK = "task"
    DECISION = "decision"
    QUESTION = "question"
    REMINDER = "reminder"
    DEADLINE = "deadline"
    FOLLOWUP = "followup"
    INFO = "info"


class ActionablePriority(str, enum.Enum):
    """Priority level for actionables"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ActionableStatus(str, enum.Enum):
    """Status of an actionable"""
    PENDING = "pending"
    ADDED_TO_TASKS = "added_to_tasks"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class FlockChannel(Base):
    """Store Flock channel/group configuration"""
    __tablename__ = "flock_channels"

    id = Column(Integer, primary_key=True, index=True)
    flock_id = Column(String(255), unique=True, nullable=False, index=True)  # Channel ID from Flock
    name = Column(String(255), nullable=False)
    type = Column(Enum(FlockChannelType), nullable=False)

    # Monitoring settings
    is_monitored = Column(Boolean, default=True)
    include_in_digest = Column(Boolean, default=True)

    # Metadata
    description = Column(Text)
    member_count = Column(Integer)
    last_synced_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("FlockMessage", back_populates="channel", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_flock_channel_monitored', 'is_monitored', 'include_in_digest'),
    )


class FlockMessage(Base):
    """Store raw messages from Flock for audit trail"""
    __tablename__ = "flock_messages"

    id = Column(Integer, primary_key=True, index=True)
    flock_message_id = Column(String(255), unique=True, nullable=False, index=True)

    # Channel/conversation details
    channel_id = Column(Integer, ForeignKey('flock_channels.id', ondelete='CASCADE'), nullable=False)

    # Message content
    text = Column(Text)
    sender_id = Column(String(255), nullable=False, index=True)  # Flock user ID
    sender_name = Column(String(255))

    # Timestamps
    sent_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Metadata
    attachments = Column(JSON)  # Store attachment metadata
    mentions = Column(JSON)  # Users mentioned in message
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)

    # Analysis status
    is_analyzed = Column(Boolean, default=False)
    analyzed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    channel = relationship("FlockChannel", back_populates="messages")
    actionables = relationship("FlockActionable", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_flock_message_sent_at', 'sent_at'),
        Index('idx_flock_message_sender', 'sender_id', 'sent_at'),
        Index('idx_flock_message_analyzed', 'is_analyzed'),
    )


class FlockActionable(Base):
    """Store actionable items extracted from Flock messages"""
    __tablename__ = "flock_actionables"

    id = Column(Integer, primary_key=True, index=True)

    # Source message
    message_id = Column(Integer, ForeignKey('flock_messages.id', ondelete='CASCADE'), nullable=False)
    digest_id = Column(Integer, ForeignKey('flock_digests.id', ondelete='SET NULL'), nullable=True)

    # Actionable details
    type = Column(Enum(ActionableType), nullable=False)
    priority = Column(Enum(ActionablePriority), default=ActionablePriority.MEDIUM)
    status = Column(Enum(ActionableStatus), default=ActionableStatus.PENDING)

    # Content
    title = Column(String(500), nullable=False)
    description = Column(Text)
    context = Column(Text)  # Additional context from conversation

    # Assignment
    assigned_to = Column(String(255))  # Flock user ID if mentioned
    assigned_to_name = Column(String(255))
    due_date = Column(DateTime)

    # LLM extraction metadata
    confidence_score = Column(Float)  # 0.0 - 1.0
    extraction_model = Column(String(100))  # Model used for extraction

    # Integration
    google_task_id = Column(String(255))  # Google Tasks ID if created
    google_task_created_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    message = relationship("FlockMessage", back_populates="actionables")
    digest = relationship("FlockDigest", back_populates="actionables")

    __table_args__ = (
        Index('idx_flock_actionable_status', 'status', 'priority'),
        Index('idx_flock_actionable_assigned', 'assigned_to', 'status'),
        Index('idx_flock_actionable_created', 'created_at'),
    )


class FlockDigest(Base):
    """Store daily digest summaries"""
    __tablename__ = "flock_digests"

    id = Column(Integer, primary_key=True, index=True)

    # Digest metadata
    digest_date = Column(DateTime, nullable=False, unique=True, index=True)  # Date of the digest

    # Time period covered
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Statistics
    total_messages_analyzed = Column(Integer, default=0)
    total_actionables_extracted = Column(Integer, default=0)
    channels_monitored = Column(Integer, default=0)

    # Breakdown by type
    tasks_count = Column(Integer, default=0)
    decisions_count = Column(Integer, default=0)
    questions_count = Column(Integer, default=0)
    reminders_count = Column(Integer, default=0)
    deadlines_count = Column(Integer, default=0)

    # Content
    summary = Column(Text)  # AI-generated summary of the day
    highlights = Column(JSON)  # Key highlights as structured data

    # Delivery
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime)
    email_recipients = Column(JSON)

    # Status
    is_generated = Column(Boolean, default=False)
    generation_started_at = Column(DateTime)
    generation_completed_at = Column(DateTime)
    generation_error = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    actionables = relationship("FlockActionable", back_populates="digest")

    __table_args__ = (
        Index('idx_flock_digest_date', 'digest_date'),
        Index('idx_flock_digest_generated', 'is_generated'),
    )


class FlockWebhook(Base):
    """Store Flock webhook configurations"""
    __tablename__ = "flock_webhooks"

    id = Column(Integer, primary_key=True, index=True)

    # Webhook details
    name = Column(String(255), nullable=False)
    webhook_type = Column(String(50), nullable=False)  # "incoming" or "outgoing"

    # For incoming webhooks (EspressoBot -> Flock)
    webhook_url = Column(Text)  # URL to send messages to
    target_channel = Column(String(255))  # Target Flock channel

    # For outgoing webhooks (Flock -> EspressoBot)
    webhook_token = Column(String(255))  # Token for authentication
    source_channel = Column(String(255))  # Source Flock channel

    # Settings
    is_active = Column(Boolean, default=True)
    use_case = Column(String(100))  # e.g., "price_monitor_alerts", "system_errors"

    # Metadata
    description = Column(Text)
    created_by = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_flock_webhook_active', 'is_active', 'use_case'),
    )
