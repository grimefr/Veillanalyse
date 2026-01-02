"""
Doppelganger Tracker - Configuration Module
============================================
Centralized configuration management using Pydantic settings.
Loads configuration from environment variables and .env files.

Usage:
    from config.settings import settings
    print(settings.database_url)
"""

from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        app_name: Application identifier
        debug: Enable debug mode
        log_level: Logging verbosity level
        database_url: PostgreSQL connection string
        redis_url: Redis connection string
        telegram_api_id: Telegram API credentials
        telegram_api_hash: Telegram API hash
        collection_interval: Seconds between collection runs
        nlp_batch_size: Number of items to process per NLP batch
        network_lookback_days: Days to look back for network analysis
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # --- Application ---
    app_name: str = Field(default="Doppelganger Tracker", description="Application name")
    debug: bool = Field(default=False, description="Debug mode flag")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # --- Database ---
    # SECURITY: No default password - MUST be set via environment variable
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection URL (auto-constructed if not provided)"
    )
    postgres_user: str = Field(default="doppelganger", description="PostgreSQL username")
    postgres_password: str = Field(..., description="PostgreSQL password (REQUIRED)")
    postgres_db: str = Field(default="doppelganger", description="PostgreSQL database name")
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    
    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    
    # --- Telegram ---
    telegram_api_id: Optional[str] = Field(default=None, description="Telegram API ID")
    telegram_api_hash: Optional[str] = Field(default=None, description="Telegram API Hash")
    telegram_session_name: str = Field(default="doppelganger_collector", description="Telethon session name")
    
    # --- Collection ---
    collection_interval: int = Field(default=300, description="Collection interval in seconds")
    initial_lookback_days: int = Field(default=7, description="Initial data lookback period")
    max_messages_per_channel: int = Field(default=100, description="Max messages per Telegram channel")
    request_timeout: int = Field(default=30, description="HTTP request timeout")
    
    # --- Analysis ---
    nlp_batch_size: int = Field(default=500, description="NLP processing batch size")
    network_lookback_days: int = Field(default=30, description="Network analysis lookback period")
    min_similarity_threshold: float = Field(default=0.5, description="Minimum similarity for propagation")
    propaganda_threshold: float = Field(default=0.7, description="Propaganda detection threshold")
    
    # --- Paths ---
    data_dir: str = Field(default="./data", description="Data directory path")
    logs_dir: str = Field(default="./logs", description="Logs directory path")
    exports_dir: str = Field(default="./exports", description="Exports directory path")
    config_dir: str = Field(default="./config", description="Config directory path")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid option."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    @property
    def telegram_configured(self) -> bool:
        """Check if Telegram credentials are configured."""
        return bool(self.telegram_api_id and self.telegram_api_hash)
    
    def get_database_url(self) -> str:
        """
        Build database URL from components if DATABASE_URL not set.

        Returns:
            str: Complete PostgreSQL connection URL

        Raises:
            ValueError: If postgres_password is not set
        """
        if not self.postgres_password:
            raise ValueError(
                "POSTGRES_PASSWORD must be set in environment variables or .env file. "
                "See .env.example for configuration template."
            )

        if self.database_url:
            return self.database_url

        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings instance.
    
    Returns:
        Settings: Application settings singleton
    """
    return Settings()


# Global settings instance for convenience
settings = get_settings()
