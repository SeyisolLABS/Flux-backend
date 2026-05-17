"""
Daily totals model for tracking spending limits.
"""
from sqlalchemy import Column, Date, Numeric, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class DailyTotal(Base):
    __tablename__ = "daily_totals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    date = Column(Date, nullable=False, index=True)
    total_sent_usdc = Column(Numeric(20, 6), default=0, nullable=False)
    transaction_count = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship
    user = relationship("User", backref="daily_totals")
    
    # Unique constraint on user_id and date
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_user_date'),
    )
    
    def __repr__(self):
        return f"<DailyTotal(user_id={self.user_id}, date={self.date}, total={self.total_sent_usdc})>"
