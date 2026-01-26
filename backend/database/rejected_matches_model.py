"""Rejected matches model for tracking blacklisted product pairs.

This model tracks product pairs that have been manually rejected/unmatched
to prevent them from being auto-matched again in the future.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class RejectedMatch(Base):
    """Tracks product pairs that have been explicitly rejected to prevent future auto-matching."""

    __tablename__ = "rejected_matches"

    id = Column(String, primary_key=True)
    idc_product_id = Column(String, ForeignKey("idc_products.id", ondelete="CASCADE"), nullable=False)
    competitor_product_id = Column(String, ForeignKey("competitor_products.id", ondelete="CASCADE"), nullable=False)
    rejected_reason = Column(Text)
    rejected_by = Column(String)  # User who rejected the match
    rejected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes for fast lookups during auto-matching
    __table_args__ = (
        Index('idx_rejected_pair', 'idc_product_id', 'competitor_product_id', unique=True),
        Index('idx_rejected_idc', 'idc_product_id'),
        Index('idx_rejected_comp', 'competitor_product_id'),
        {"extend_existing": True}
    )
