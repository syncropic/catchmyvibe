"""Playlist API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.database import get_session
from api.schemas import (
    PlaylistCreate,
    PlaylistDetailResponse,
    PlaylistResponse,
    PlaylistUpdate,
    TrackResponse,
)
from models import Playlist, PlaylistTrack, Track

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.get("", response_model=list[PlaylistResponse])
async def list_playlists(
    parent_id: Optional[str] = Query(None, description="Filter by parent playlist ID"),
    source: Optional[str] = Query(None, description="Filter by source"),
    include_folders: bool = Query(True, description="Include folder playlists"),
    session: AsyncSession = Depends(get_session),
) -> list[PlaylistResponse]:
    """List playlists with optional filtering."""
    stmt = select(Playlist)

    if parent_id is not None:
        stmt = stmt.where(Playlist.parent_id == parent_id)
    elif parent_id is None:
        # Default to root level playlists
        stmt = stmt.where(Playlist.parent_id.is_(None))

    if source:
        stmt = stmt.where(Playlist.source == source)

    if not include_folders:
        stmt = stmt.where(Playlist.is_folder == False)  # noqa: E712

    stmt = stmt.order_by(Playlist.name)
    result = await session.execute(stmt)
    playlists = result.scalars().all()

    return [PlaylistResponse.model_validate(p) for p in playlists]


@router.get("/{playlist_id}", response_model=PlaylistDetailResponse)
async def get_playlist(
    playlist_id: str,
    session: AsyncSession = Depends(get_session),
) -> PlaylistDetailResponse:
    """Get a playlist by ID with tracks."""
    stmt = (
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(selectinload(Playlist.children), selectinload(Playlist.tracks))
    )
    result = await session.execute(stmt)
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Fetch tracks in order
    tracks_stmt = (
        select(Track)
        .join(PlaylistTrack)
        .where(PlaylistTrack.playlist_id == playlist_id)
        .order_by(PlaylistTrack.position)
    )
    tracks_result = await session.execute(tracks_stmt)
    tracks = tracks_result.scalars().all()

    response = PlaylistDetailResponse.model_validate(playlist)
    response.tracks = [TrackResponse.model_validate(t) for t in tracks]
    response.children = [PlaylistResponse.model_validate(c) for c in playlist.children]

    return response


@router.post("", response_model=PlaylistResponse, status_code=201)
async def create_playlist(
    playlist_data: PlaylistCreate,
    session: AsyncSession = Depends(get_session),
) -> PlaylistResponse:
    """Create a new playlist."""
    # Verify parent exists if specified
    if playlist_data.parent_id:
        stmt = select(Playlist).where(Playlist.id == playlist_data.parent_id)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Parent playlist not found")

    playlist = Playlist(source="manual", **playlist_data.model_dump())
    session.add(playlist)
    await session.flush()
    await session.refresh(playlist)
    return PlaylistResponse.model_validate(playlist)


@router.patch("/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(
    playlist_id: str,
    playlist_data: PlaylistUpdate,
    session: AsyncSession = Depends(get_session),
) -> PlaylistResponse:
    """Update a playlist."""
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    result = await session.execute(stmt)
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    update_data = playlist_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(playlist, field, value)

    await session.flush()
    await session.refresh(playlist)
    return PlaylistResponse.model_validate(playlist)


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a playlist."""
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    result = await session.execute(stmt)
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    await session.delete(playlist)


# Playlist tracks management
@router.post("/{playlist_id}/tracks/{track_id}", status_code=201)
async def add_track_to_playlist(
    playlist_id: str,
    track_id: str,
    position: Optional[int] = Query(None, description="Position in playlist (appends if not specified)"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Add a track to a playlist."""
    # Verify playlist exists
    playlist_stmt = select(Playlist).where(Playlist.id == playlist_id)
    playlist_result = await session.execute(playlist_stmt)
    playlist = playlist_result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Verify track exists
    track_stmt = select(Track).where(Track.id == track_id)
    track_result = await session.execute(track_stmt)
    track = track_result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Check if track already in playlist
    existing_stmt = select(PlaylistTrack).where(
        PlaylistTrack.playlist_id == playlist_id,
        PlaylistTrack.track_id == track_id,
    )
    existing_result = await session.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Track already in playlist")

    # Get position if not specified
    if position is None:
        max_pos_stmt = select(func.max(PlaylistTrack.position)).where(
            PlaylistTrack.playlist_id == playlist_id
        )
        max_pos_result = await session.execute(max_pos_stmt)
        max_pos = max_pos_result.scalar() or 0
        position = max_pos + 1

    # Create playlist track
    playlist_track = PlaylistTrack(
        playlist_id=playlist_id,
        track_id=track_id,
        position=position,
    )
    session.add(playlist_track)

    # Update playlist stats
    playlist.track_count = playlist.track_count + 1
    if track.duration_ms:
        playlist.total_duration_ms = playlist.total_duration_ms + track.duration_ms

    await session.flush()
    return {"message": "Track added to playlist", "position": position}


@router.delete("/{playlist_id}/tracks/{track_id}", status_code=204)
async def remove_track_from_playlist(
    playlist_id: str,
    track_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove a track from a playlist."""
    stmt = select(PlaylistTrack).where(
        PlaylistTrack.playlist_id == playlist_id,
        PlaylistTrack.track_id == track_id,
    )
    result = await session.execute(stmt)
    playlist_track = result.scalar_one_or_none()

    if not playlist_track:
        raise HTTPException(status_code=404, detail="Track not in playlist")

    # Update playlist stats
    playlist_stmt = select(Playlist).where(Playlist.id == playlist_id)
    playlist_result = await session.execute(playlist_stmt)
    playlist = playlist_result.scalar_one_or_none()
    if playlist:
        playlist.track_count = max(0, playlist.track_count - 1)
        # Get track duration for stats update
        track_stmt = select(Track).where(Track.id == track_id)
        track_result = await session.execute(track_stmt)
        track = track_result.scalar_one_or_none()
        if track and track.duration_ms:
            playlist.total_duration_ms = max(0, playlist.total_duration_ms - track.duration_ms)

    await session.delete(playlist_track)


@router.patch("/{playlist_id}/tracks/reorder", status_code=200)
async def reorder_playlist_tracks(
    playlist_id: str,
    track_ids: list[str],
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reorder tracks in a playlist by providing the new order of track IDs."""
    # Verify playlist exists
    playlist_stmt = select(Playlist).where(Playlist.id == playlist_id)
    playlist_result = await session.execute(playlist_stmt)
    if not playlist_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Get existing playlist tracks
    stmt = select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)
    result = await session.execute(stmt)
    playlist_tracks = {pt.track_id: pt for pt in result.scalars().all()}

    # Update positions
    for position, track_id in enumerate(track_ids, start=1):
        if track_id in playlist_tracks:
            playlist_tracks[track_id].position = position

    await session.flush()
    return {"message": "Playlist reordered", "track_count": len(track_ids)}
