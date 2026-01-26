"""
Database package for conversation persistence and price monitoring
"""

from .models import (
    Base,
    Conversation,
    Message,
    Memory,
    UserPreference,
    DatabaseManager,
    User,
    DailyAnalyticsCache,
    HourlyAnalyticsCache,
    AnalyticsSyncStatus
)

from .operations import (
    ConversationOps,
    MessageOps,
    MemoryOps,
    UserPreferenceOps
)

# Import price monitor models
from .price_monitor_models import (
    Competitor,
    CompetitorProduct,
    ScrapeJob,
    IdcProduct,
    MonitoredBrand,
    MonitoredCollection,
    ProductMatch,
    PriceAlert,
    PriceHistory,
    ViolationHistory,
    RejectedMatch
)

# Import Flock models
from .flock_models import (
    FlockChannel,
    FlockMessage,
    FlockActionable,
    FlockDigest,
    FlockWebhook,
    FlockChannelType,
    ActionableType,
    ActionablePriority,
    ActionableStatus
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

    # Operations
    'ConversationOps',
    'MessageOps',
    'MemoryOps',
    'UserPreferenceOps',

    # Price Monitor Models
    'Competitor',
    'CompetitorProduct',
    'ScrapeJob',
    'IdcProduct',
    'MonitoredBrand',
    'MonitoredCollection',
    'ProductMatch',
    'PriceAlert',
    'PriceHistory',
    'ViolationHistory',
    'RejectedMatch',
    'DailyAnalyticsCache',
    'HourlyAnalyticsCache',
    'AnalyticsSyncStatus',

    # Flock Models
    'FlockChannel',
    'FlockMessage',
    'FlockActionable',
    'FlockDigest',
    'FlockWebhook',
    'FlockChannelType',
    'ActionableType',
    'ActionablePriority',
    'ActionableStatus'
]