"""
Authentication service with JWT tokens and Argon2 password hashing.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.hash import argon2
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User
from app.models.session import Session as SessionModel
from app.utils.exceptions import InvalidCredentialsException, UserAlreadyExistsException
from app.utils.validators import validate_username, validate_email, validate_password
import uuid
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using Argon2.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return argon2.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        try:
            return argon2.verify(plain_password, hashed_password)
        except Exception:
            return False
    
    @staticmethod
    def create_access_token(user_id: str) -> str:
        """
        Create JWT access token.
        
        Args:
            user_id: User ID
            
        Returns:
            JWT access token
        """
        expires = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "exp": expires,
            "type": "access"
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """
        Create JWT refresh token.
        
        Args:
            user_id: User ID
            
        Returns:
            JWT refresh token
        """
        expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user_id),
            "exp": expires,
            "type": "refresh"
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[str]:
        """
        Verify JWT token and extract user ID.
        
        Args:
            token: JWT token
            token_type: Expected token type
            
        Returns:
            User ID if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            
            # Verify token type
            if payload.get("type") != token_type:
                return None
            
            # Extract user ID
            user_id: str = payload.get("sub")
            return user_id
        
        except JWTError:
            return None
    
    @staticmethod
    async def create_user(
        db: Session,
        username: str,
        email: str,
        password: str,
        wallet_id: str,
        wallet_address: str
    ) -> User:
        """
        Create a new user with validated inputs.
        
        Args:
            db: Database session
            username: Username (validated)
            email: Email (validated)
            password: Password (validated)
            wallet_id: Circle wallet ID
            wallet_address: Wallet address
            
        Returns:
            Created user
            
        Raises:
            UserAlreadyExistsException: If username or email exists
        """
        # Check if user exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                raise UserAlreadyExistsException("username")
            else:
                raise UserAlreadyExistsException("email")
        
        # Hash password
        password_hash = AuthService.hash_password(password)
        
        # Create user
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            wallet_id=wallet_id,
            wallet_address=wallet_address,
            verification_level=0,
            email_verified=False,
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info("User created: %s", username)
        return user
    
    @staticmethod
    async def authenticate_user(db: Session, username_or_email: str, password: str) -> Optional[User]:
        """
        Authenticate user with username/email and password.
        
        Args:
            db: Database session
            username_or_email: Username or email
            password: Password
            
        Returns:
            User if authenticated, None otherwise
        """
        # Find user by username or email
        user = db.query(User).filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()
        
        if not user:
            return None
        
        # Verify password
        if not AuthService.verify_password(password, user.password_hash):
            return None
        
        # Check if user is active
        if not user.is_active:
            return None
        
        return user
    
    @staticmethod
    async def create_session(
        db: Session,
        user_id: uuid.UUID,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SessionModel:
        """
        Create a new session.
        
        Args:
            db: Database session
            user_id: User ID
            refresh_token: Refresh token
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Created session
        """
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        session = SessionModel(
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return session


# Global service instance
auth_service = AuthService()
