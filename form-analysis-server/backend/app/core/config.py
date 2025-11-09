"""Application configuration management using Pydantic Settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Uses Pydantic Settings for type validation and automatic loading
    from .env files and environment variables.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database settings - Fixed to PostgreSQL only
    database_url: str = Field(
        default="postgresql+asyncpg://app:app_secure_password@localhost:5432/form_analysis_db",
        description="PostgreSQL database connection URL (固定使用PostgreSQL)"
    )
    
    # API server settings
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API server port")
    
    # File upload settings
    max_upload_size_mb: int = Field(
        default=10, 
        ge=1, 
        le=100, 
        description="Maximum file upload size in MB"
    )
    upload_temp_dir: str = Field(
        default="./uploads", 
        description="Temporary directory for file uploads"
    )
    allowed_extensions: list[str] = Field(
        default=["csv", "xlsx"], 
        description="Allowed file extensions"
    )
    max_concurrent_uploads: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent upload operations"
    )
    
    # CORS settings (using string for environment variable compatibility)
    cors_origins_str: str = Field(
        default="http://localhost:5173,http://localhost:3000", 
        description="Comma-separated CORS origins",
        alias="CORS_ORIGINS"
    )
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    
    # Development settings
    debug: bool = Field(default=False, description="Enable debug mode")
    reload: bool = Field(default=False, description="Enable auto-reload (development)")
    environment: str = Field(default="production", description="Application environment")
    
    # Security settings
    secret_key: str = Field(
        default="qI5s1RT9GCr8wlqnfh1XxOZBO_47lSqedali3vHGOVk",
        min_length=32,
        description="Secret key for JWT and other crypto operations"
    )
    
    # Database connection pool settings
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy SQL logging")
    database_pool_size: int = Field(default=5, ge=1, description="Database connection pool size")
    database_pool_recycle: int = Field(default=3600, ge=300, description="Database pool recycle time in seconds")
    db_pool_size: int = Field(default=5, ge=1, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, ge=0, description="Database max overflow connections")
    db_pool_timeout: int = Field(default=30, ge=1, description="Database pool timeout seconds")
    
    # Performance settings
    request_timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    health_check_interval: int = Field(default=30, ge=5, description="Health check interval")
    
    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from the string configuration."""
        if not self.cors_origins_str.strip():
            return ["http://localhost:5173", "http://localhost:3000"]
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]
    
    @field_validator("allowed_extensions", mode="before")  
    @classmethod
    def parse_allowed_extensions(cls, v: Any) -> list[str]:
        """Parse allowed extensions from string or list."""
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(",") if ext.strip()]
        return v
    
    @field_validator("upload_temp_dir")
    @classmethod
    def ensure_upload_dir_exists(cls, v: str) -> str:
        """Ensure upload directory exists."""
        Path(v).mkdir(parents=True, exist_ok=True)
        return v
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Get maximum upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.debug or self.reload or os.getenv("DEV_MODE", "false").lower() == "true"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses lru_cache to ensure settings are loaded only once
    and cached for subsequent calls.
    """
    return Settings()