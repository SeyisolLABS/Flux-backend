"""
Payment schemas with validation.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from decimal import Decimal
from app.utils.validators import validate_amount, validate_recipient, sanitize_note


class SendPaymentRequest(BaseModel):
    """Send payment request with validation"""
    recipient: str = Field(..., description="@username or 0x... wallet address")
    amount_usdc: float = Field(..., gt=0, description="Amount in USDC")
    note: Optional[str] = Field(None, max_length=500, description="Optional payment note")
    
    @validator('recipient')
    def validate_recipient_format(cls, v):
        # Returns tuple (type, value) but we only need validation
        validate_recipient(v)
        return v
    
    @validator('amount_usdc')
    def validate_amount_value(cls, v):
        return validate_amount(v)
    
    @validator('note')
    def sanitize_note_content(cls, v):
        return sanitize_note(v)


class TransactionResponse(BaseModel):
    """Transaction response"""
    id: str
    sender_address: Optional[str]
    recipient_address: str
    amount_usdc: str
    fee_usdc: str
    status: str
    tx_hash: Optional[str]
    note: Optional[str]
    finality_time_ms: Optional[int]
    created_at: str
    confirmed_at: Optional[str]
    
    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """Paginated transaction list"""
    transactions: list[TransactionResponse]
    total: int
    page: int
    pages: int
