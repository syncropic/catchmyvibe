"""DJ Session models for tracking live sets."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDMixin


class DJSession(Base, UUIDMixin, TimestampMixin):
    """Represents a DJ set/session."""

    __tablename__ = "dj_sessions"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    venue: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # club, festival, lounge, warmup, etc.

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Session metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    energy_profile: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # build, peak, sustain, etc.
    genre_focus: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Recording
    recording_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_recorded: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Stats computed after session
    track_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bpm_range: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # {min, max}

    # Relationships
    tracks: Mapped[list["SessionTrack"]] = relationship(
        "SessionTrack", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DJSession(id={self.id}, name='{self.name}', venue='{self.venue}')>"


class SessionTrack(Base, UUIDMixin, TimestampMixin):
    """A track played during a DJ session."""

    __tablename__ = "session_tracks"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("dj_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track_id: Mapped[str] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Play info
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    played_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    play_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # BPM at play time (might differ from track's original BPM due to tempo adjustment)
    played_bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Transition info
    transition_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # blend, cut, echo_out, etc.
    transition_quality: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 1-5 rating
    transition_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Crowd reaction (if tracked)
    crowd_energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-1

    # If track wasn't in catalog, store basic info
    unmatched_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    unmatched_artist: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    session: Mapped["DJSession"] = relationship("DJSession", back_populates="tracks")
    track: Mapped[Optional["Track"]] = relationship("Track")

    def __repr__(self) -> str:
        return f"<SessionTrack(session_id={self.session_id}, position={self.position})>"


# Import Track for type hints
from models.track import Track
