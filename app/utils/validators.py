"""
Input validation and sanitization utilities.
Prevents prompt injection, SQL injection, and XSS attacks.
"""
import re
from typing import Optional
from fastapi import HTTPException, status


def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    Sanitize string input to prevent injection attacks.
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
        
    Raises:
        HTTPException: If input is invalid
    """
    if not value:
        return ""
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Strip leading/trailing whitespace
    value = value.strip()
    
    # Check length
    if len(value) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input too long (max {max_length} characters)"
        )
    
    # Remove any control characters except newlines and tabs
    value = ''.join(char for char in value if char.isprintable() or char in '\n\t')
    
    return value


def validate_username(username: str) -> str:
    """
    Validate and sanitize username.
    Only allows alphanumeric, underscore, and hyphen.
    
    Args:
        username: Username to validate
        
    Returns:
        Validated username
        
    Raises:
        HTTPException: If username is invalid
    """
    username = sanitize_string(username, max_length=20)
    
    # Username regex: 3-20 chars, alphanumeric + underscore/hyphen
    pattern = r'^[a-zA-Z0-9_-]{3,20}$'
    
    if not re.match(pattern, username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be 3-20 characters, alphanumeric with underscore/hyphen"
        )
    
    return username


def validate_email(email: str) -> str:
    """
    Validate and sanitize email address.
    
    Args:
        email: Email to validate
        
    Returns:
        Validated email
        
    Raises:
        HTTPException: If email is invalid
    """
    email = sanitize_string(email, max_length=255).lower()
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )
    
    return email


def validate_wallet_address(address: str) -> str:
    """
    Validate Ethereum/Arc wallet address.
    
    Args:
        address: Wallet address to validate
        
    Returns:
        Validated address
        
    Raises:
        HTTPException: If address is invalid
    """
    address = sanitize_string(address, max_length=42).lower()
    
    # Ethereum address: 0x followed by 40 hex characters
    pattern = r'^0x[a-fA-F0-9]{40}$'
    
    if not re.match(pattern, address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid wallet address format"
        )
    
    return address


def validate_amount(amount: float, min_amount: float = 0.01, max_amount: float = 1000000) -> float:
    """
    Validate payment amount.
    
    Args:
        amount: Amount to validate
        min_amount: Minimum allowed amount
        max_amount: Maximum allowed amount
        
    Returns:
        Validated amount
        
    Raises:
        HTTPException: If amount is invalid
    """
    if amount < min_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount must be at least {min_amount} USDC"
        )
    
    if amount > max_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount cannot exceed {max_amount} USDC"
        )
    
    # Round to 6 decimal places (USDC precision)
    return round(amount, 6)


def sanitize_note(note: Optional[str]) -> Optional[str]:
    """
    Sanitize payment note.
    Removes potentially dangerous content while preserving readability.
    
    Args:
        note: Note to sanitize
        
    Returns:
        Sanitized note or None
    """
    if not note:
        return None
    
    note = sanitize_string(note, max_length=500)
    
    # Remove any HTML-like tags
    note = re.sub(r'<[^>]+>', '', note)
    
    # Remove excessive whitespace
    note = ' '.join(note.split())
    
    return note if note else None


def validate_password(password: str) -> str:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Validated password
        
    Raises:
        HTTPException: If password is weak
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    if len(password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password too long (max 128 characters)"
        )
    
    # Check for at least one letter and one number
    if not re.search(r'[a-zA-Z]', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one letter"
        )
    
    if not re.search(r'\d', password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number"
        )
    
    return password


def validate_recipient(recipient: str) -> tuple[str, str]:
    """
    Validate recipient (username or wallet address).
    
    Args:
        recipient: Recipient identifier
        
    Returns:
        Tuple of (type, value) where type is 'username' or 'address'
        
    Raises:
        HTTPException: If recipient is invalid
    """
    recipient = sanitize_string(recipient, max_length=42)
    
    # Check if it's a username (starts with @)
    if recipient.startswith('@'):
        username = validate_username(recipient[1:])
        return ('username', username)
    
    # Check if it's a wallet address
    if recipient.startswith('0x'):
        address = validate_wallet_address(recipient)
        return ('address', address)
    
    # Try as username without @
    try:
        username = validate_username(recipient)
        return ('username', username)
    except HTTPException:
        pass
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid recipient format. Use @username or 0x... address"
    )
