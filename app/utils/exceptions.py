"""
Custom exception classes for the application.
"""
from fastapi import HTTPException, status


class InsufficientBalanceException(HTTPException):
    """Raised when user doesn't have enough balance"""
    def __init__(self, required: float, available: float):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. Required: {required} USDC, Available: {available} USDC"
        )


class TransactionLimitExceededException(HTTPException):
    """Raised when transaction exceeds limits"""
    def __init__(self, limit: float, amount: float):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction amount ({amount} USDC) exceeds limit ({limit} USDC)"
        )


class DailyLimitExceededException(HTTPException):
    """Raised when daily limit is exceeded"""
    def __init__(self, limit: float, current: float, amount: float):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Daily limit exceeded. Limit: {limit} USDC, Current: {current} USDC, Attempted: {amount} USDC"
        )


class UserNotFoundException(HTTPException):
    """Raised when user is not found"""
    def __init__(self, identifier: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {identifier}"
        )


class WalletNotFoundException(HTTPException):
    """Raised when wallet is not found"""
    def __init__(self, wallet_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet not found: {wallet_id}"
        )


class InvalidCredentialsException(HTTPException):
    """Raised when credentials are invalid"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


class UserAlreadyExistsException(HTTPException):
    """Raised when trying to create duplicate user"""
    def __init__(self, field: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with this {field} already exists"
        )


class CircleAPIException(HTTPException):
    """Raised when Circle API fails"""
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Circle API error: {message}"
        )


class ArcNetworkException(HTTPException):
    """Raised when Arc Network fails"""
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Arc Network error: {message}"
        )


class RateLimitExceededException(HTTPException):
    """Raised when rate limit is exceeded"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
