"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


# Track schemas
class CuePointBase(BaseModel):
    """Base cue point schema."""

    position_ms: int
    name: Optional[str] = None
    color: Optional[str] = None
    cue_type: str = "cue"
    loop_end_ms: Optional[int] = None
    source: str = "manual"


class CuePointCreate(CuePointBase):
    """Schema for creating a cue point."""

    pass


class CuePointResponse(CuePointBase, BaseSchema):
    """Schema for cue point response."""

    id: str
    track_id: str
    created_at: datetime


class SourceLinkBase(BaseModel):
    """Base source link schema."""

    source: str
    external_id: Optional[str] = None
    uri: Optional[str] = None
    file_path: Optional[str] = None
    is_primary: bool = False


class SourceLinkResponse(SourceLinkBase, BaseSchema):
    """Schema for source link response."""

    id: str
    track_id: str


class TrackBase(BaseModel):
    """Base track schema."""

    title: str
    artists: list[str] = Field(default_factory=list)
    album: Optional[str] = None
    isrc: Optional[str] = None
    label: Optional[str] = None
    release_year: Optional[int] = None
    genre: Optional[str] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    duration_ms: Optional[int] = None


class TrackCreate(TrackBase):
    """Schema for creating a track."""

    cloud_uri: Optional[str] = None
    original_path: Optional[str] = None
    streaming_ids: dict = Field(default_factory=dict)


class TrackUpdate(BaseModel):
    """Schema for updating a track."""

    title: Optional[str] = None
    artists: Optional[list[str]] = None
    album: Optional[str] = None
    isrc: Optional[str] = None
    label: Optional[str] = None
    release_year: Optional[int] = None
    genre: Optional[str] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    duration_ms: Optional[int] = None
    energy: Optional[float] = None
    danceability: Optional[float] = None
    valence: Optional[float] = None
    vibe_tags: Optional[list[str]] = None
    mix_in_point_ms: Optional[int] = None
    mix_out_point_ms: Optional[int] = None
    rating: Optional[int] = None
    comment: Optional[str] = None


class TrackResponse(TrackBase, BaseSchema):
    """Schema for track response."""

    id: str
    energy: Optional[float] = None
    danceability: Optional[float] = None
    valence: Optional[float] = None
    acousticness: Optional[float] = None
    instrumentalness: Optional[float] = None
    speechiness: Optional[float] = None
    liveness: Optional[float] = None
    loudness: Optional[float] = None
    vibe_tags: list[str] = Field(default_factory=list)
    mix_in_point_ms: Optional[int] = None
    mix_out_point_ms: Optional[int] = None
    rating: Optional[int] = None
    play_count: int = 0
    comment: Optional[str] = None
    cloud_uri: Optional[str] = None
    streaming_ids: dict = Field(default_factory=dict)
    is_analyzed: bool = False
    is_enriched: bool = False
    created_at: datetime
    updated_at: datetime


class TrackDetailResponse(TrackResponse):
    """Detailed track response with cue points and sources."""

    cue_points: list[CuePointResponse] = Field(default_factory=list)
    source_links: list[SourceLinkResponse] = Field(default_factory=list)


class TrackListResponse(BaseSchema):
    """Paginated track list response."""

    items: list[TrackResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Playlist schemas
class PlaylistBase(BaseModel):
    """Base playlist schema."""

    name: str
    description: Optional[str] = None
    is_folder: bool = False


class PlaylistCreate(PlaylistBase):
    """Schema for creating a playlist."""

    parent_id: Optional[str] = None


class PlaylistUpdate(BaseModel):
    """Schema for updating a playlist."""

    name: Optional[str] = None
    description: Optional[str] = None


class PlaylistResponse(PlaylistBase, BaseSchema):
    """Schema for playlist response."""

    id: str
    source: str
    parent_id: Optional[str] = None
    track_count: int = 0
    total_duration_ms: int = 0
    cover_art_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PlaylistDetailResponse(PlaylistResponse):
    """Detailed playlist response with tracks."""

    tracks: list[TrackResponse] = Field(default_factory=list)
    children: list["PlaylistResponse"] = Field(default_factory=list)


# Session schemas
class SessionTrackBase(BaseModel):
    """Base session track schema."""

    track_id: Optional[str] = None
    position: int
    played_bpm: Optional[float] = None
    transition_type: Optional[str] = None
    transition_quality: Optional[int] = None
    transition_notes: Optional[str] = None
    crowd_energy: Optional[float] = None


class SessionTrackCreate(SessionTrackBase):
    """Schema for adding a track to a session."""

    unmatched_title: Optional[str] = None
    unmatched_artist: Optional[str] = None


class SessionTrackResponse(SessionTrackBase, BaseSchema):
    """Schema for session track response."""

    id: str
    session_id: str
    played_at: Optional[datetime] = None
    play_duration_ms: Optional[int] = None
    track: Optional[TrackResponse] = None


class DJSessionBase(BaseModel):
    """Base DJ session schema."""

    name: str
    venue: Optional[str] = None
    event_type: Optional[str] = None
    planned_duration_ms: Optional[int] = None
    notes: Optional[str] = None
    energy_profile: Optional[str] = None
    genre_focus: list[str] = Field(default_factory=list)


class DJSessionCreate(DJSessionBase):
    """Schema for creating a DJ session."""

    pass


class DJSessionUpdate(BaseModel):
    """Schema for updating a DJ session."""

    name: Optional[str] = None
    venue: Optional[str] = None
    event_type: Optional[str] = None
    notes: Optional[str] = None
    energy_profile: Optional[str] = None


class DJSessionResponse(DJSessionBase, BaseSchema):
    """Schema for DJ session response."""

    id: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    is_recorded: bool = False
    track_count: int = 0
    avg_bpm: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class DJSessionDetailResponse(DJSessionResponse):
    """Detailed DJ session response with tracks."""

    tracks: list[SessionTrackResponse] = Field(default_factory=list)


# Import/Sync schemas
class ImportJobBase(BaseModel):
    """Base import job schema."""

    source: str  # rekordbox, serato, spotify, tidal
    status: str = "pending"


class ImportJobCreate(ImportJobBase):
    """Schema for creating an import job."""

    file_path: Optional[str] = None  # For Rekordbox XML or Serato DB


class ImportJobResponse(ImportJobBase, BaseSchema):
    """Schema for import job response."""

    id: str
    tracks_imported: int = 0
    tracks_skipped: int = 0
    tracks_failed: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Analysis schemas
class AnalysisJobCreate(BaseModel):
    """Schema for creating an analysis job."""

    track_ids: list[str]
    force: bool = False  # Re-analyze even if already analyzed


class AnalysisJobResponse(BaseModel):
    """Schema for analysis job response."""

    job_id: str
    tracks_queued: int
    message: str


class EnrichmentJobCreate(BaseModel):
    """Schema for creating an enrichment job."""

    track_ids: Optional[list[str]] = None  # None means all un-enriched tracks


class EnrichmentJobResponse(BaseModel):
    """Schema for enrichment job response."""

    job_id: str
    tracks_queued: int
    message: str


# Search/Filter schemas
class TrackSearchParams(BaseModel):
    """Parameters for searching tracks."""

    query: Optional[str] = None
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    key: Optional[str] = None
    keys: Optional[list[str]] = None  # Multiple keys (for harmonic mixing)
    energy_min: Optional[float] = None
    energy_max: Optional[float] = None
    genre: Optional[str] = None
    genres: Optional[list[str]] = None
    vibe_tags: Optional[list[str]] = None
    is_analyzed: Optional[bool] = None
    is_enriched: Optional[bool] = None
    sort_by: str = "title"
    sort_order: str = "asc"
    page: int = 1
    page_size: int = 50


class SimilarTrackRequest(BaseModel):
    """Request for finding similar tracks."""

    track_id: str
    limit: int = 10
    bpm_range: float = 6.0  # +/- BPM tolerance
    same_key: bool = False  # Require same key
    harmonic_keys: bool = True  # Include harmonically compatible keys


class SimilarTrackResponse(BaseModel):
    """Response for similar tracks."""

    source_track: TrackResponse
    similar_tracks: list[TrackResponse]
    similarity_scores: list[float]


# Health check
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
    redis: str
