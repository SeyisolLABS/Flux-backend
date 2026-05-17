"""
Wallet API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models.user import User
from app.api.payments import get_current_user
from app.services.circle_service import circle_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/balance")
@limiter.limit("60/minute")
async def get_wallet_balance(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get wallet balance.
    
    Rate limit: 60 requests per minute
    """
    try:
        if not current_user.wallet_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found"
            )
        
        # Get balance from Circle
        balance = await circle_service.get_balance(current_user.wallet_id)
        
        return {
            "balance_usdc": balance,
            "wallet_address": current_user.wallet_address,
            "wallet_id": current_user.wallet_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Balance fetch error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch balance"
        ) from e


@router.get("/info")
@limiter.limit("60/minute")
async def get_wallet_info(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get wallet information.
    
    Rate limit: 60 requests per minute
    """
    return {
        "wallet_address": current_user.wallet_address,
        "wallet_id": current_user.wallet_id,
        "verification_level": current_user.verification_level
    }
