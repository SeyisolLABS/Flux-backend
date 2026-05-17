"""
Payment API endpoints with validation and rate limiting.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.schemas.payment import SendPaymentRequest, TransactionResponse, TransactionListResponse
from app.services.payment_service import payment_service
from app.utils.validators import validate_recipient, validate_amount, sanitize_note
from app.models.user import User
from app.models.transaction import Transaction
from app.services.auth_service import auth_service
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    
    # Verify token
    user_id = auth_service.verify_token(token, token_type="access")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user


@router.post("/send", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute")  # Rate limit: 30 payments per minute
async def send_payment(
    request: Request,
    payment_data: SendPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send USDC payment.
    
    Rate limit: 30 payments per minute per user
    Returns 202 Accepted immediately, processing happens async
    """
    try:
        logger.info(f"Payment request from {current_user.username} to {payment_data.recipient}")
        
        # Validate and sanitize inputs
        recipient_type, recipient_value = validate_recipient(payment_data.recipient)
        amount = validate_amount(payment_data.amount_usdc)
        note = sanitize_note(payment_data.note)
        
        # Resolve recipient
        recipient_user, recipient_address = await payment_service.resolve_recipient(
            db=db,
            recipient=recipient_value
        )
        
        # Check limits
        await payment_service.check_limits(
            db=db,
            user=current_user,
            amount=amount
        )
        
        # Check balance
        await payment_service.check_balance(
            user=current_user,
            amount=amount
        )
        
        # Create transaction record (status: pending)
        transaction = Transaction(
            sender_id=current_user.id,
            recipient_id=recipient_user.id if recipient_user else None,
            amount_usdc=amount,
            fee_usdc=0.01,
            status="pending",
            sender_address=current_user.wallet_address,
            recipient_address=recipient_address,
            note=note
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        # TODO: Trigger Celery task for async processing
        # For now, we'll process synchronously
        from app.services.circle_service import circle_service
        
        try:
            # Execute transfer via Circle
            result = await circle_service.send_usdc(
                from_wallet_id=current_user.wallet_id,
                to_address=recipient_address,
                amount=str(amount)
            )
            
            # Update transaction
            transaction.status = "confirmed"
            transaction.tx_hash = result.get("tx_hash")
            transaction.finality_time_ms = 300  # Arc Network ~300ms
            
            from datetime import datetime
            transaction.confirmed_at = datetime.utcnow()
            
            db.commit()
            
            # Update daily total
            await payment_service.update_daily_total(
                db=db,
                user_id=current_user.id,
                amount=amount
            )
            
            logger.info(f"Payment successful: {transaction.id}")
            
        except Exception as e:
            logger.error(f"Payment failed: {str(e)}")
            transaction.status = "failed"
            transaction.error_message = str(e)
            db.commit()
            raise
        
        return {
            "transaction_id": str(transaction.id),
            "status": transaction.status,
            "message": "Payment processed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        )


@router.get("/history", response_model=TransactionListResponse)
@limiter.limit("60/minute")
async def get_transaction_history(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transaction history with pagination.
    
    Rate limit: 60 requests per minute
    """
    try:
        # Build query
        query = db.query(Transaction).filter(
            (Transaction.sender_id == current_user.id) | 
            (Transaction.recipient_id == current_user.id)
        )
        
        # Apply status filter
        if status_filter:
            query = query.filter(Transaction.status == status_filter)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        transactions = query.order_by(
            Transaction.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        # Format response
        transaction_list = []
        for tx in transactions:
            transaction_list.append({
                "id": str(tx.id),
                "sender_address": tx.sender_address,
                "recipient_address": tx.recipient_address,
                "amount_usdc": str(tx.amount_usdc),
                "fee_usdc": str(tx.fee_usdc),
                "status": tx.status,
                "tx_hash": tx.tx_hash,
                "note": tx.note,
                "finality_time_ms": tx.finality_time_ms,
                "created_at": tx.created_at.isoformat(),
                "confirmed_at": tx.confirmed_at.isoformat() if tx.confirmed_at else None
            })
        
        pages = (total + limit - 1) // limit
        page = (offset // limit) + 1
        
        return {
            "transactions": transaction_list,
            "total": total,
            "page": page,
            "pages": pages
        }
    
    except Exception as e:
        logger.error(f"Transaction history error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch transaction history"
        )


@router.get("/{transaction_id}", response_model=TransactionResponse)
@limiter.limit("60/minute")
async def get_transaction_details(
    request: Request,
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transaction details by ID.
    
    Rate limit: 60 requests per minute
    """
    try:
        # Validate UUID
        try:
            tx_uuid = uuid.UUID(transaction_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid transaction ID format"
            )
        
        # Get transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == tx_uuid,
            (Transaction.sender_id == current_user.id) | 
            (Transaction.recipient_id == current_user.id)
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        return {
            "id": str(transaction.id),
            "sender_address": transaction.sender_address,
            "recipient_address": transaction.recipient_address,
            "amount_usdc": str(transaction.amount_usdc),
            "fee_usdc": str(transaction.fee_usdc),
            "status": transaction.status,
            "tx_hash": transaction.tx_hash,
            "note": transaction.note,
            "finality_time_ms": transaction.finality_time_ms,
            "created_at": transaction.created_at.isoformat(),
            "confirmed_at": transaction.confirmed_at.isoformat() if transaction.confirmed_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transaction details error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch transaction details"
        )
