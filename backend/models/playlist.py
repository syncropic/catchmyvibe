"""Playlist and crate models."""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin


class Playlist(Base, UUIDMixin, TimestampMixin):
    """Playlist/crate model for organizing tracks."""

    __tablename__ = "playlists"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # rekordbox, serato, spotify, manual
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_folder: Mapped[bool] = mapped_column(default=False, nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), nullable=True
    )

    # Playlist metadata
    cover_art_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    track_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    parent: Mapped[Optional["Playlist"]] = relationship(
        "Playlist", remote_side="Playlist.id", back_populates="children"
    )
    children: Mapped[list["Playlist"]] = relationship(
        "Playlist", back_populates="parent", cascade="all, delete-orphan"
    )
    tracks: Mapped[list["PlaylistTrack"]] = relationship(
        "PlaylistTrack", back_populates="playlist", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Playlist(id={self.id}, name='{self.name}', source={self.source})>"


class PlaylistTrack(Base, UUIDMixin, TimestampMixin):
    """Association between playlists and tracks with ordering."""

    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[str] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Additional metadata
    added_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="tracks")
    track: Mapped["Track"] = relationship("Track")

    def __repr__(self) -> str:
        return f"<PlaylistTrack(playlist_id={self.playlist_id}, track_id={self.track_id}, pos={self.position})>"


# Import Track for type hints
from models.track import Track
