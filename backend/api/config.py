"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "CatchMyVibe"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/catchmyvibe"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Supabase (optional, for cloud deployment)
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # Google Drive
    google_drive_credentials_file: Optional[str] = None
    google_drive_folder_id: Optional[str] = None

    # Backblaze B2
    b2_application_key_id: Optional[str] = None
    b2_application_key: Optional[str] = None
    b2_bucket_name: Optional[str] = None

    # AWS S3 (if using S3-compatible storage)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_bucket_name: Optional[str] = None

    # Spotify
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    spotify_redirect_uri: str = "http://localhost:8000/api/auth/spotify/callback"

    # Tidal
    tidal_client_id: Optional[str] = None
    tidal_client_secret: Optional[str] = None

    # Analysis
    analysis_temp_dir: str = "/tmp/catchmyvibe_analysis"
    max_concurrent_analysis: int = 4
    analysis_timeout_seconds: int = 300

    # API Settings
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Auth (for future use)
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
