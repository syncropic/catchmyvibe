"""Track and related models."""

from enum import Enum
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin


class TrackSource(str, Enum):
    """Enumeration of track sources."""

    LOCAL = "local"
    REKORDBOX = "rekordbox"
    SERATO = "serato"
    SPOTIFY = "spotify"
    TIDAL = "tidal"
    BEATPORT = "beatport"
    GOOGLE_DRIVE = "google_drive"
    BACKBLAZE = "backblaze"


class Track(Base, UUIDMixin, TimestampMixin):
    """Main track model representing a unique piece of music."""

    __tablename__ = "tracks"

    # Identity
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    artists: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    album: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    isrc: Mapped[Optional[str]] = mapped_column(
        String(12), nullable=True, unique=True, index=True
    )
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    release_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Audio Properties
    bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    key: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Analysis Results (computed)
    energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    danceability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    valence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    acousticness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    instrumentalness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speechiness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liveness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loudness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ML-generated tags and embeddings
    vibe_tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    embedding: Mapped[Optional[list[float]]] = mapped_column(ARRAY(Float), nullable=True)

    # DJ Metadata
    mix_in_point_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mix_out_point_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Storage locations
    cloud_uri: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    original_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # External IDs for streaming services
    streaming_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Waveform data for visualization (downsampled)
    waveform_data: Mapped[Optional[list[float]]] = mapped_column(ARRAY(Float), nullable=True)

    # Analysis status
    is_analyzed: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_enriched: Mapped[bool] = mapped_column(default=False, nullable=False)
    analysis_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    cue_points: Mapped[list["CuePoint"]] = relationship(
        "CuePoint", back_populates="track", cascade="all, delete-orphan"
    )
    source_links: Mapped[list["SourceLink"]] = relationship(
        "SourceLink", back_populates="track", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        artists_str = ", ".join(self.artists) if self.artists else "Unknown"
        return f"<Track(id={self.id}, title='{self.title}', artists='{artists_str}')>"


class CuePoint(Base, UUIDMixin, TimestampMixin):
    """Cue point markers within a track."""

    __tablename__ = "cue_points"

    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    cue_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="cue"
    )  # cue, loop, memory
    loop_end_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # rekordbox, serato, manual

    # Relationship
    track: Mapped["Track"] = relationship("Track", back_populates="cue_points")

    def __repr__(self) -> str:
        return f"<CuePoint(track_id={self.track_id}, position_ms={self.position_ms}, type={self.cue_type})>"


class SourceLink(Base, UUIDMixin, TimestampMixin):
    """Links a track to its various sources (platforms, files)."""

    __tablename__ = "source_links"

    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # TrackSource value
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    uri: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationship
    track: Mapped["Track"] = relationship("Track", back_populates="source_links")

    def __repr__(self) -> str:
        return f"<SourceLink(track_id={self.track_id}, source={self.source})>"
