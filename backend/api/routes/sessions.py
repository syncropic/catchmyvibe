"""DJ Session API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import get_session
from api.schemas import (
    DJSessionCreate,
    DJSessionDetailResponse,
    DJSessionResponse,
    DJSessionUpdate,
    SessionTrackCreate,
    SessionTrackResponse,
    TrackResponse,
)
from models import DJSession, SessionTrack, Track

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[DJSessionResponse])
async def list_sessions(
    venue: Optional[str] = Query(None, description="Filter by venue"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[DJSessionResponse]:
    """List DJ sessions with optional filtering."""
    stmt = select(DJSession)

    if venue:
        stmt = stmt.where(DJSession.venue.ilike(f"%{venue}%"))
    if event_type:
        stmt = stmt.where(DJSession.event_type == event_type)

    stmt = stmt.order_by(DJSession.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    sessions = result.scalars().all()

    return [DJSessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=DJSessionDetailResponse)
async def get_session_by_id(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> DJSessionDetailResponse:
    """Get a DJ session by ID with all tracks."""
    stmt = (
        select(DJSession)
        .where(DJSession.id == session_id)
        .options(selectinload(DJSession.tracks))
    )
    result = await db_session.execute(stmt)
    dj_session = result.scalar_one_or_none()

    if not dj_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch tracks in order with track details
    tracks_stmt = (
        select(SessionTrack, Track)
        .outerjoin(Track, SessionTrack.track_id == Track.id)
        .where(SessionTrack.session_id == session_id)
        .order_by(SessionTrack.position)
    )
    tracks_result = await db_session.execute(tracks_stmt)
    track_data = tracks_result.all()

    session_tracks = []
    for session_track, track in track_data:
        st_response = SessionTrackResponse.model_validate(session_track)
        if track:
            st_response.track = TrackResponse.model_validate(track)
        session_tracks.append(st_response)

    response = DJSessionDetailResponse.model_validate(dj_session)
    response.tracks = session_tracks
    return response


@router.post("", response_model=DJSessionResponse, status_code=201)
async def create_session(
    session_data: DJSessionCreate,
    db_session: AsyncSession = Depends(get_session),
) -> DJSessionResponse:
    """Create a new DJ session."""
    dj_session = DJSession(**session_data.model_dump())
    db_session.add(dj_session)
    await db_session.flush()
    await db_session.refresh(dj_session)
    return DJSessionResponse.model_validate(dj_session)


@router.patch("/{session_id}", response_model=DJSessionResponse)
async def update_session(
    session_id: str,
    session_data: DJSessionUpdate,
    db_session: AsyncSession = Depends(get_session),
) -> DJSessionResponse:
    """Update a DJ session."""
    stmt = select(DJSession).where(DJSession.id == session_id)
    result = await db_session.execute(stmt)
    dj_session = result.scalar_one_or_none()

    if not dj_session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_data = session_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dj_session, field, value)

    await db_session.flush()
    await db_session.refresh(dj_session)
    return DJSessionResponse.model_validate(dj_session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a DJ session."""
    stmt = select(DJSession).where(DJSession.id == session_id)
    result = await db_session.execute(stmt)
    dj_session = result.scalar_one_or_none()

    if not dj_session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db_session.delete(dj_session)


# Session control endpoints
@router.post("/{session_id}/start", response_model=DJSessionResponse)
async def start_session(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> DJSessionResponse:
    """Start a DJ session (set start time to now)."""
    stmt = select(DJSession).where(DJSession.id == session_id)
    result = await db_session.execute(stmt)
    dj_session = result.scalar_one_or_none()

    if not dj_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if dj_session.started_at:
        raise HTTPException(status_code=400, detail="Session already started")

    dj_session.started_at = datetime.now(timezone.utc)
    await db_session.flush()
    await db_session.refresh(dj_session)
    return DJSessionResponse.model_validate(dj_session)


@router.post("/{session_id}/end", response_model=DJSessionResponse)
async def end_session(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> DJSessionResponse:
    """End a DJ session (set end time to now and calculate stats)."""
    stmt = select(DJSession).where(DJSession.id == session_id)
    result = await db_session.execute(stmt)
    dj_session = result.scalar_one_or_none()

    if not dj_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if dj_session.ended_at:
        raise HTTPException(status_code=400, detail="Session already ended")

    dj_session.ended_at = datetime.now(timezone.utc)

    # Calculate stats
    tracks_stmt = (
        select(SessionTrack, Track)
        .outerjoin(Track, SessionTrack.track_id == Track.id)
        .where(SessionTrack.session_id == session_id)
    )
    tracks_result = await db_session.execute(tracks_stmt)
    track_data = tracks_result.all()

    dj_session.track_count = len(track_data)

    bpms = []
    for session_track, track in track_data:
        bpm = session_track.played_bpm or (track.bpm if track else None)
        if bpm:
            bpms.append(bpm)

    if bpms:
        dj_session.avg_bpm = sum(bpms) / len(bpms)
        dj_session.bpm_range = {"min": min(bpms), "max": max(bpms)}

    await db_session.flush()
    await db_session.refresh(dj_session)
    return DJSessionResponse.model_validate(dj_session)


# Session tracks management
@router.get("/{session_id}/tracks", response_model=list[SessionTrackResponse])
async def list_session_tracks(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> list[SessionTrackResponse]:
    """List all tracks in a session."""
    stmt = (
        select(SessionTrack, Track)
        .outerjoin(Track, SessionTrack.track_id == Track.id)
        .where(SessionTrack.session_id == session_id)
        .order_by(SessionTrack.position)
    )
    result = await db_session.execute(stmt)
    track_data = result.all()

    session_tracks = []
    for session_track, track in track_data:
        st_response = SessionTrackResponse.model_validate(session_track)
        if track:
            st_response.track = TrackResponse.model_validate(track)
        session_tracks.append(st_response)

    return session_tracks


@router.post("/{session_id}/tracks", response_model=SessionTrackResponse, status_code=201)
async def add_track_to_session(
    session_id: str,
    track_data: SessionTrackCreate,
    db_session: AsyncSession = Depends(get_session),
) -> SessionTrackResponse:
    """Add a track to a DJ session."""
    # Verify session exists
    session_stmt = select(DJSession).where(DJSession.id == session_id)
    session_result = await db_session.execute(session_stmt)
    dj_session = session_result.scalar_one_or_none()
    if not dj_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify track exists if track_id is provided
    track = None
    if track_data.track_id:
        track_stmt = select(Track).where(Track.id == track_data.track_id)
        track_result = await db_session.execute(track_stmt)
        track = track_result.scalar_one_or_none()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

    # Get next position if not specified
    position = track_data.position
    if position == 0:
        max_pos_stmt = select(func.max(SessionTrack.position)).where(
            SessionTrack.session_id == session_id
        )
        max_pos_result = await db_session.execute(max_pos_stmt)
        max_pos = max_pos_result.scalar() or 0
        position = max_pos + 1

    session_track = SessionTrack(
        session_id=session_id,
        played_at=datetime.now(timezone.utc),
        **track_data.model_dump(exclude={"position"}),
    )
    session_track.position = position

    db_session.add(session_track)
    await db_session.flush()
    await db_session.refresh(session_track)

    response = SessionTrackResponse.model_validate(session_track)
    if track:
        response.track = TrackResponse.model_validate(track)

    return response


@router.patch("/{session_id}/tracks/{session_track_id}", response_model=SessionTrackResponse)
async def update_session_track(
    session_id: str,
    session_track_id: str,
    transition_type: Optional[str] = None,
    transition_quality: Optional[int] = None,
    transition_notes: Optional[str] = None,
    crowd_energy: Optional[float] = None,
    db_session: AsyncSession = Depends(get_session),
) -> SessionTrackResponse:
    """Update a session track (e.g., add transition notes)."""
    stmt = select(SessionTrack).where(
        SessionTrack.id == session_track_id,
        SessionTrack.session_id == session_id,
    )
    result = await db_session.execute(stmt)
    session_track = result.scalar_one_or_none()

    if not session_track:
        raise HTTPException(status_code=404, detail="Session track not found")

    if transition_type is not None:
        session_track.transition_type = transition_type
    if transition_quality is not None:
        session_track.transition_quality = transition_quality
    if transition_notes is not None:
        session_track.transition_notes = transition_notes
    if crowd_energy is not None:
        session_track.crowd_energy = crowd_energy

    await db_session.flush()
    await db_session.refresh(session_track)

    response = SessionTrackResponse.model_validate(session_track)

    # Fetch track if available
    if session_track.track_id:
        track_stmt = select(Track).where(Track.id == session_track.track_id)
        track_result = await db_session.execute(track_stmt)
        track = track_result.scalar_one_or_none()
        if track:
            response.track = TrackResponse.model_validate(track)

    return response
