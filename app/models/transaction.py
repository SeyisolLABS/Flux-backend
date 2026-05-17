"""
Transaction database model.
"""
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Sender/Recipient
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Amounts
    amount_usdc = Column(Numeric(20, 6), nullable=False)
    fee_usdc = Column(Numeric(20, 6), default=0.01, nullable=False)
    
    # Status
    status = Column(String(20), default="pending", nullable=False, index=True)
    
    # Blockchain data
    tx_hash = Column(String(66), unique=True, nullable=True, index=True)
    sender_address = Column(String(42), nullable=True)
    recipient_address = Column(String(42), nullable=False)
    
    # Metadata
    note = Column(Text, nullable=True)
    finality_time_ms = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], backref="sent_transactions")
    recipient = relationship("User", foreign_keys=[recipient_id], backref="received_transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount_usdc}, status={self.status})>"
