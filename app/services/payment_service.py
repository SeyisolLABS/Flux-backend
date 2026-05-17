"""
Payment service with transaction limits and validation.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
from datetime import date
from typing import Tuple
from app.models.user import User
from app.models.transaction import Transaction
from app.models.daily_total import DailyTotal
from app.config import settings
from app.utils.exceptions import (
    InsufficientBalanceException,
    TransactionLimitExceededException,
    DailyLimitExceededException,
    UserNotFoundException
)
from app.services.circle_service import circle_service
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    """Payment processing service"""
    
    @staticmethod
    def get_limits_for_level(level: int) -> Tuple[float, float]:
        """
        Get transaction and daily limits for verification level.
        
        Args:
            level: Verification level (0-3)
            
        Returns:
            Tuple of (max_transaction, max_daily)
        """
        if level == 0:
            return (
                settings.MAX_TRANSACTION_AMOUNT_LEVEL_0,
                settings.MAX_DAILY_AMOUNT_LEVEL_0
            )
        elif level == 1:
            return (
                settings.MAX_TRANSACTION_AMOUNT_LEVEL_1,
                settings.MAX_DAILY_AMOUNT_LEVEL_1
            )
        elif level == 2:
            return (
                settings.MAX_TRANSACTION_AMOUNT_LEVEL_2,
                settings.MAX_DAILY_AMOUNT_LEVEL_2
            )
        else:
            # Level 3: Unlimited
            return (float('inf'), float('inf'))
    
    @staticmethod
    async def check_limits(
        db: Session,
        user: User,
        amount: float
    ) -> None:
        """
        Check if transaction is within limits.
        
        Args:
            db: Database session
            user: User making payment
            amount: Transaction amount
            
        Raises:
            TransactionLimitExceededException: If transaction exceeds limit
            DailyLimitExceededException: If daily limit exceeded
        """
        max_transaction, max_daily = PaymentService.get_limits_for_level(user.verification_level)
        
        # Check transaction limit
        if amount > max_transaction:
            raise TransactionLimitExceededException(max_transaction, amount)
        
        # Get today's total
        today = date.today()
        daily_total = db.query(DailyTotal).filter(
            DailyTotal.user_id == user.id,
            DailyTotal.date == today
        ).first()
        
        current_total = float(daily_total.total_sent_usdc) if daily_total else 0.0
        
        # Check daily limit
        if current_total + amount > max_daily:
            raise DailyLimitExceededException(max_daily, current_total, amount)
    
    @staticmethod
    async def check_balance(
        user: User,
        amount: float
    ) -> None:
        """
        Check if user has sufficient balance.
        
        Args:
            user: User
            amount: Amount to send (including fee)
            
        Raises:
            InsufficientBalanceException: If balance is insufficient
        """
        if not user.wallet_id:
            raise InsufficientBalanceException(amount, 0.0)
        
        # Get balance from Circle
        balance_str = await circle_service.get_balance(user.wallet_id)
        balance = float(balance_str)
        
        # Include fee in check
        total_required = amount + 0.01
        
        if balance < total_required:
            raise InsufficientBalanceException(total_required, balance)
    
    @staticmethod
    async def resolve_recipient(
        db: Session,
        recipient: str
    ) -> Tuple[User, str]:
        """
        Resolve recipient username to user and address.
        
        Args:
            db: Database session
            recipient: Username or wallet address
            
        Returns:
            Tuple of (User or None, wallet_address)
            
        Raises:
            UserNotFoundException: If username not found
        """
        # Remove @ if present
        if recipient.startswith('@'):
            recipient = recipient[1:]
        
        # Check if it's a wallet address
        if recipient.startswith('0x'):
            # Try to find user by address
            user = db.query(User).filter(User.wallet_address == recipient).first()
            return (user, recipient)
        
        # It's a username
        user = db.query(User).filter(User.username == recipient).first()
        
        if not user:
            raise UserNotFoundException(recipient)
        
        if not user.wallet_address:
            raise ValueError(f"User @{recipient} does not have a wallet")
        
        return (user, user.wallet_address)
    
    @staticmethod
    async def update_daily_total(
        db: Session,
        user_id: str,
        amount: float
    ) -> None:
        """
        Update daily spending total.
        
        Args:
            db: Database session
            user_id: User ID
            amount: Transaction amount
        """
        today = date.today()
        
        # Get or create daily total
        daily_total = db.query(DailyTotal).filter(
            DailyTotal.user_id == user_id,
            DailyTotal.date == today
        ).first()
        
        if daily_total:
            daily_total.total_sent_usdc += Decimal(str(amount))
            daily_total.transaction_count += 1
        else:
            daily_total = DailyTotal(
                user_id=user_id,
                date=today,
                total_sent_usdc=amount,
                transaction_count=1
            )
            db.add(daily_total)
        
        db.commit()


# Global service instance
payment_service = PaymentService()
