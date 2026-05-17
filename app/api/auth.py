"""
Authentication API endpoints with rate limiting and input sanitization.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, RefreshTokenRequest
from app.services.auth_service import auth_service
from app.services.circle_service import circle_service
from app.utils.validators import validate_username, validate_email, validate_password
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")  # Strict rate limit for signup
async def signup(
    request: Request,
    signup_data: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    User signup with automatic wallet creation.
    
    Rate limit: 5 signups per hour per IP
    """
    try:
        # Validate inputs (already validated by Pydantic, but double-check)
        username = validate_username(signup_data.username)
        email = validate_email(signup_data.email)
        password = validate_password(signup_data.password)
        
        logger.info(f"Signup attempt: {username}, {email}")
        
        # Create Circle wallet first
        wallet_data = await circle_service.create_wallet(username)
        
        if not wallet_data.get("wallet_id") or not wallet_data.get("address"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create wallet. Please try again."
            )
        
        # Create user in database
        user = await auth_service.create_user(
            db=db,
            username=username,
            email=email,
            password=password,
            wallet_id=wallet_data["wallet_id"],
            wallet_address=wallet_data["address"]
        )
        
        # Create tokens
        access_token = auth_service.create_access_token(str(user.id))
        refresh_token = auth_service.create_refresh_token(str(user.id))
        
        # Create session
        await auth_service.create_session(
            db=db,
            user_id=user.id,
            refresh_token=refresh_token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        logger.info(f"User created successfully: {username}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "wallet_address": user.wallet_address,
                "verification_level": user.verification_level
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signup failed. Please try again."
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")  # Rate limit for login
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    User login with JWT tokens.
    
    Rate limit: 10 login attempts per minute per IP
    """
    try:
        logger.info(f"Login attempt: {login_data.username}")
        
        # Authenticate user
        user = await auth_service.authenticate_user(
            db=db,
            username_or_email=login_data.username,
            password=login_data.password
        )
        
        if not user:
            logger.warning(f"Failed login attempt: {login_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create tokens
        access_token = auth_service.create_access_token(str(user.id))
        refresh_token = auth_service.create_refresh_token(str(user.id))
        
        # Create session
        await auth_service.create_session(
            db=db,
            user_id=user.id,
            refresh_token=refresh_token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        logger.info(f"User logged in: {user.username}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "wallet_address": user.wallet_address,
                "verification_level": user.verification_level
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    Rate limit: 20 refresh attempts per minute
    """
    try:
        # Verify refresh token
        user_id = auth_service.verify_token(refresh_data.refresh_token, token_type="refresh")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        new_access_token = auth_service.create_access_token(str(user.id))
        new_refresh_token = auth_service.create_refresh_token(str(user.id))
        
        # Update session
        await auth_service.create_session(
            db=db,
            user_id=user.id,
            refresh_token=new_refresh_token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        logger.info(f"Token refreshed for user: {user.username}")
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "wallet_address": user.wallet_address,
                "verification_level": user.verification_level
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Refresh token error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )
