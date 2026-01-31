"""Track API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import get_session
from api.schemas import (
    CuePointCreate,
    CuePointResponse,
    SimilarTrackRequest,
    SimilarTrackResponse,
    TrackCreate,
    TrackDetailResponse,
    TrackListResponse,
    TrackResponse,
    TrackSearchParams,
    TrackUpdate,
)
from models import CuePoint, Track

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.get("", response_model=TrackListResponse)
async def list_tracks(
    query: Optional[str] = Query(None, description="Search query for title/artist"),
    bpm_min: Optional[float] = Query(None, ge=0),
    bpm_max: Optional[float] = Query(None, le=300),
    key: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    is_analyzed: Optional[bool] = Query(None),
    is_enriched: Optional[bool] = Query(None),
    sort_by: str = Query("title", enum=["title", "bpm", "key", "created_at", "updated_at"]),
    sort_order: str = Query("asc", enum=["asc", "desc"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> TrackListResponse:
    """List tracks with filtering, sorting, and pagination."""
    stmt = select(Track)

    # Apply filters
    if query:
        search_term = f"%{query}%"
        stmt = stmt.where(
            or_(
                Track.title.ilike(search_term),
                func.array_to_string(Track.artists, ", ").ilike(search_term),
                Track.album.ilike(search_term),
            )
        )

    if bpm_min is not None:
        stmt = stmt.where(Track.bpm >= bpm_min)
    if bpm_max is not None:
        stmt = stmt.where(Track.bpm <= bpm_max)
    if key:
        stmt = stmt.where(Track.key == key)
    if genre:
        stmt = stmt.where(Track.genre.ilike(f"%{genre}%"))
    if is_analyzed is not None:
        stmt = stmt.where(Track.is_analyzed == is_analyzed)
    if is_enriched is not None:
        stmt = stmt.where(Track.is_enriched == is_enriched)

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    # Apply sorting
    sort_column = getattr(Track, sort_by, Track.title)
    if sort_order == "desc":
        stmt = stmt.order_by(sort_column.desc())
    else:
        stmt = stmt.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await session.execute(stmt)
    tracks = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return TrackListResponse(
        items=[TrackResponse.model_validate(t) for t in tracks],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{track_id}", response_model=TrackDetailResponse)
async def get_track(
    track_id: str,
    session: AsyncSession = Depends(get_session),
) -> TrackDetailResponse:
    """Get a track by ID with full details."""
    stmt = (
        select(Track)
        .where(Track.id == track_id)
        .options(selectinload(Track.cue_points), selectinload(Track.source_links))
    )
    result = await session.execute(stmt)
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    return TrackDetailResponse.model_validate(track)


@router.post("", response_model=TrackResponse, status_code=201)
async def create_track(
    track_data: TrackCreate,
    session: AsyncSession = Depends(get_session),
) -> TrackResponse:
    """Create a new track."""
    track = Track(**track_data.model_dump())
    session.add(track)
    await session.flush()
    await session.refresh(track)
    return TrackResponse.model_validate(track)


@router.patch("/{track_id}", response_model=TrackResponse)
async def update_track(
    track_id: str,
    track_data: TrackUpdate,
    session: AsyncSession = Depends(get_session),
) -> TrackResponse:
    """Update a track."""
    stmt = select(Track).where(Track.id == track_id)
    result = await session.execute(stmt)
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    update_data = track_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(track, field, value)

    await session.flush()
    await session.refresh(track)
    return TrackResponse.model_validate(track)


@router.delete("/{track_id}", status_code=204)
async def delete_track(
    track_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a track."""
    stmt = select(Track).where(Track.id == track_id)
    result = await session.execute(stmt)
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    await session.delete(track)


# Cue points
@router.get("/{track_id}/cue-points", response_model=list[CuePointResponse])
async def list_cue_points(
    track_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[CuePointResponse]:
    """List cue points for a track."""
    stmt = select(CuePoint).where(CuePoint.track_id == track_id).order_by(CuePoint.position_ms)
    result = await session.execute(stmt)
    cue_points = result.scalars().all()
    return [CuePointResponse.model_validate(cp) for cp in cue_points]


@router.post("/{track_id}/cue-points", response_model=CuePointResponse, status_code=201)
async def create_cue_point(
    track_id: str,
    cue_point_data: CuePointCreate,
    session: AsyncSession = Depends(get_session),
) -> CuePointResponse:
    """Create a cue point for a track."""
    # Verify track exists
    stmt = select(Track).where(Track.id == track_id)
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Track not found")

    cue_point = CuePoint(track_id=track_id, **cue_point_data.model_dump())
    session.add(cue_point)
    await session.flush()
    await session.refresh(cue_point)
    return CuePointResponse.model_validate(cue_point)


@router.delete("/{track_id}/cue-points/{cue_point_id}", status_code=204)
async def delete_cue_point(
    track_id: str,
    cue_point_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a cue point."""
    stmt = select(CuePoint).where(CuePoint.id == cue_point_id, CuePoint.track_id == track_id)
    result = await session.execute(stmt)
    cue_point = result.scalar_one_or_none()

    if not cue_point:
        raise HTTPException(status_code=404, detail="Cue point not found")

    await session.delete(cue_point)


# Similarity search
@router.post("/similar", response_model=SimilarTrackResponse)
async def find_similar_tracks(
    request: SimilarTrackRequest,
    session: AsyncSession = Depends(get_session),
) -> SimilarTrackResponse:
    """Find tracks similar to a given track."""
    # Get source track
    stmt = select(Track).where(Track.id == request.track_id)
    result = await session.execute(stmt)
    source_track = result.scalar_one_or_none()

    if not source_track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Build query for similar tracks
    stmt = select(Track).where(Track.id != request.track_id)

    # BPM range filter
    if source_track.bpm:
        stmt = stmt.where(
            Track.bpm.between(
                source_track.bpm - request.bpm_range,
                source_track.bpm + request.bpm_range,
            )
        )

    # Key filter
    if request.same_key and source_track.key:
        stmt = stmt.where(Track.key == source_track.key)
    elif request.harmonic_keys and source_track.key:
        harmonic_keys = get_harmonic_keys(source_track.key)
        stmt = stmt.where(Track.key.in_(harmonic_keys))

    stmt = stmt.limit(request.limit)
    result = await session.execute(stmt)
    similar_tracks = result.scalars().all()

    # Calculate simple similarity scores (placeholder for embedding-based similarity)
    similarity_scores = [0.8] * len(similar_tracks)  # TODO: Use embeddings

    return SimilarTrackResponse(
        source_track=TrackResponse.model_validate(source_track),
        similar_tracks=[TrackResponse.model_validate(t) for t in similar_tracks],
        similarity_scores=similarity_scores,
    )


def get_harmonic_keys(key: str) -> list[str]:
    """Get harmonically compatible keys using Camelot wheel."""
    camelot_wheel = {
        # Major keys
        "1A": ["1A", "12A", "2A", "1B"],
        "2A": ["2A", "1A", "3A", "2B"],
        "3A": ["3A", "2A", "4A", "3B"],
        "4A": ["4A", "3A", "5A", "4B"],
        "5A": ["5A", "4A", "6A", "5B"],
        "6A": ["6A", "5A", "7A", "6B"],
        "7A": ["7A", "6A", "8A", "7B"],
        "8A": ["8A", "7A", "9A", "8B"],
        "9A": ["9A", "8A", "10A", "9B"],
        "10A": ["10A", "9A", "11A", "10B"],
        "11A": ["11A", "10A", "12A", "11B"],
        "12A": ["12A", "11A", "1A", "12B"],
        # Minor keys
        "1B": ["1B", "12B", "2B", "1A"],
        "2B": ["2B", "1B", "3B", "2A"],
        "3B": ["3B", "2B", "4B", "3A"],
        "4B": ["4B", "3B", "5B", "4A"],
        "5B": ["5B", "4B", "6B", "5A"],
        "6B": ["6B", "5B", "7B", "6A"],
        "7B": ["7B", "6B", "8B", "7A"],
        "8B": ["8B", "7B", "9B", "8A"],
        "9B": ["9B", "8B", "10B", "9A"],
        "10B": ["10B", "9B", "11B", "10A"],
        "11B": ["11B", "10B", "12B", "11A"],
        "12B": ["12B", "11B", "1B", "12A"],
    }
    return camelot_wheel.get(key.upper(), [key])
