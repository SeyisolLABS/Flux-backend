"""
Users API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models.user import User
from app.api.payments import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/profile")
@limiter.limit("60/minute")
async def get_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile.
    
    Rate limit: 60 requests per minute
    """
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "wallet_address": current_user.wallet_address,
        "verification_level": current_user.verification_level,
        "email_verified": current_user.email_verified,
        "created_at": current_user.created_at.isoformat()
    }


@router.get("/{username}")
@limiter.limit("60/minute")
async def get_user_by_username(
    request: Request,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Get public user info by username.
    
    Rate limit: 60 requests per minute
    """
    try:
        # Remove @ if present
        if username.startswith('@'):
            username = username[1:]
        
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Return only public info
        return {
            "username": user.username,
            "wallet_address": user.wallet_address,
            "verification_level": user.verification_level
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user"
        )
