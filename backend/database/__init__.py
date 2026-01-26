"""
Database package for Nifty Strategist v2
"""

from .models import (
    Base,
    Conversation,
    Message,
    Memory,
    UserPreference,
    DatabaseManager,
    User,
    Run,
    AIModel,
    Permission,
    Role,
    DocChunk,
    UserMCPServer,
    UserMCPOAuthToken,
    Note,
    PublishedNote,
    # Trading models
    Trade,
    AgentDecision,
    WatchlistItem,
    TradeStatus,
    TradeDirection,
)

from .operations import (
    ConversationOps,
    MessageOps,
    MemoryOps,
    UserPreferenceOps
)

__all__ = [
    # Core Models
    'Base',
    'Conversation',
    'Message',
    'Memory',
    'UserPreference',
    'DatabaseManager',
    'User',
    'Run',
    'AIModel',
    'Permission',
    'Role',
    'DocChunk',
    'UserMCPServer',
    'UserMCPOAuthToken',
    'Note',
    'PublishedNote',

    # Trading Models
    'Trade',
    'AgentDecision',
    'WatchlistItem',
    'TradeStatus',
    'TradeDirection',

    # Operations
    'ConversationOps',
    'MessageOps',
    'MemoryOps',
    'UserPreferenceOps',
]
