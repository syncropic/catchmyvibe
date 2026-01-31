"""Authentication and token storage models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDMixin


class StreamingServiceToken(Base, UUIDMixin, TimestampMixin):
    """Stores OAuth tokens for streaming services (Spotify, Tidal, etc.)."""

    __tablename__ = "streaming_service_tokens"

    service: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # spotify, tidal

    # User info from the service
    service_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    service_user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    service_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # OAuth tokens (encrypted in production)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(50), nullable=False, default="Bearer")

    # Token expiry
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scopes granted
    scopes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sync stats
    tracks_synced: Mapped[int] = mapped_column(default=0, nullable=False)
    playlists_synced: Mapped[int] = mapped_column(default=0, nullable=False)

    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(self.expires_at.tzinfo) >= self.expires_at

    def __repr__(self) -> str:
        return f"<StreamingServiceToken(service={self.service}, user={self.service_user_email})>"
