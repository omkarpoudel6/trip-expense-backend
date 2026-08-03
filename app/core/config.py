"""
Application configuration, loaded from environment variables / .env file.

Never hardcode secrets here. Everything sensitive comes from the environment
so local, CI, and production can each supply their own values.
"""

from functools import lru_cache

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # ---------- App -----------
    APP_NAME: str = "Trip Expense Tracker API"
    ENVIRONMENT: str = "development" # development | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # ---------- Database -----------
    DATABASE_URL: PostgresDsn
    
    # ---------- Auth / JWT -----------
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # ----------- CORS --------------
    CORS_ORIGINS: list[str] = ["*"]
    
    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        if not v or v == "changeme":
            raise ValueError(
                "JWT_SECRET_KEY must be set to a real secret. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        return v
    
@lru_cache
def get_settings() -> Settings:
    """ Cached so we don't re-parse the environment on every request."""
    return Settings() # type: ignore[call-arg]

settings = get_settings()
    
    