"""
Authentication schemas with input validation.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from app.utils.validators import validate_username, validate_password


class SignupRequest(BaseModel):
    """User signup request with validation"""
    username: str = Field(..., min_length=3, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    
    @validator('username')
    def validate_username_format(cls, v):
        return validate_username(v)
    
    @validator('password')
    def validate_password_strength(cls, v):
        return validate_password(v)


class LoginRequest(BaseModel):
    """User login request"""
    username: str  # Can be username or email
    password: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        return validate_password(v)
