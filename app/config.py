"""
Application configuration using environment variables.
All sensitive data is stored in environment variables, never hardcoded.
"""
from pydantic_settings import BaseSettings
from typing import List
import os
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "FLUX"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # JWT Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Circle API (NEVER hardcode these!)
    CIRCLE_API_KEY: str
    CIRCLE_ENTITY_SECRET: str
    CIRCLE_API_BASE_URL: str = "https://api.circle.com/v1"
    CIRCLE_WALLET_SET_ID: str
    
    # Arc Network
    ARC_RPC_URL: str
    ARC_CHAIN_ID: int = 98765
    ARC_EXPLORER_URL: str = "https://explorer.arc-testnet.network"
    
    # Email SMTP
    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str
    SMTP_FROM_NAME: str = "FLUX"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Sentry
    SENTRY_DSN: str = ""
    
    # Transaction Limits by Verification Level
    MAX_TRANSACTION_AMOUNT_LEVEL_0: float = 100.0
    MAX_DAILY_AMOUNT_LEVEL_0: float = 1000.0
    MAX_TRANSACTION_AMOUNT_LEVEL_1: float = 500.0
    MAX_DAILY_AMOUNT_LEVEL_1: float = 5000.0
    MAX_TRANSACTION_AMOUNT_LEVEL_2: float = 5000.0
    MAX_DAILY_AMOUNT_LEVEL_2: float = 50000.0
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Settings are loaded once and cached for performance.
    """
    return Settings()


# Global settings instance
settings = get_settings()
