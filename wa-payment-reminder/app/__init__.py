"""
Application configuration using pydantic-settings.
Loads all environment variables with type safety.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str

    # Meta Cloud API
    wa_phone_number_id: str
    wa_access_token: str
    wa_webhook_verify_token: str

    # Redis
    upstash_redis_url: str

    # App
    port: int = 8000
    app_env: str = "development"
    app_base_url: str = ""

    # Scheduler
    scheduler_hour: int = 8
    scheduler_minute: int = 0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance - imported by other modules
settings = Settings()
