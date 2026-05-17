"""
API routes package.
"""
from app.api import auth, payments, wallet, notifications, users

__all__ = [
    "auth",
    "payments",
    "wallet",
    "notifications",
    "users",
]
