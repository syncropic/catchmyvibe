"""Spotify library sync functionality."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Track, SourceLink, StreamingServiceToken


@dataclass
class SyncProgress:
    """Progress tracking for sync operations."""

    job_id: str
    status: str  # pending, syncing, completed, failed
    total_tracks: int = 0
    processed_tracks: int = 0
    new_tracks: int = 0
    updated_tracks: int = 0
    skipped_tracks: int = 0
    failed_tracks: int = 0
    current_offset: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Global sync jobs tracking (use Redis in production)
sync_jobs: dict[str, SyncProgress] = {}


class SpotifySyncService:
    """Service for syncing Spotify library to local catalog."""

    SPOTIFY_API_BASE = "https://api.spotify.com/v1"
    BATCH_SIZE = 50  # Spotify's max limit per request

    # Pitch class to Camelot wheel mapping
    PITCH_CLASS_TO_CAMELOT = {
        (0, 1): "8B", (0, 0): "5A",
        (1, 1): "3B", (1, 0): "12A",
        (2, 1): "10B", (2, 0): "7A",
        (3, 1): "5B", (3, 0): "2A",
        (4, 1): "12B", (4, 0): "9A",
        (5, 1): "7B", (5, 0): "4A",
        (6, 1): "2B", (6, 0): "11A",
        (7, 1): "9B", (7, 0): "6A",
        (8, 1): "4B", (8, 0): "1A",
        (9, 1): "11B", (9, 0): "8A",
        (10, 1): "6B", (10, 0): "3A",
        (11, 1): "1B", (11, 0): "10A",
    }

    def __init__(self, access_token: str):
        """Initialize with Spotify access token."""
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {access_token}"}

    async def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated request to Spotify API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.SPOTIFY_API_BASE}{endpoint}",
                headers=self.headers,
                params=params,
            )

            if response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(response.headers.get("Retry-After", 1))
                await asyncio.sleep(retry_after)
                return await self._request(endpoint, params)

            response.raise_for_status()
            return response.json()

    async def get_liked_songs_count(self) -> int:
        """Get total number of liked songs."""
        data = await self._request("/me/tracks", {"limit": 1})
        return data.get("total", 0)

    async def fetch_liked_songs_page(self, offset: int = 0, limit: int = 50) -> dict:
        """Fetch a page of liked songs."""
        return await self._request("/me/tracks", {"limit": limit, "offset": offset})

    async def fetch_audio_features_batch(self, track_ids: list[str]) -> list[dict]:
        """Fetch audio features for multiple tracks."""
        if not track_ids:
            return []

        # Spotify allows max 100 IDs per request
        ids_param = ",".join(track_ids[:100])
        data = await self._request("/audio-features", {"ids": ids_param})
        return data.get("audio_features", [])

    async def sync_liked_songs(
        self,
        session: AsyncSession,
        token: StreamingServiceToken,
        job_id: str,
    ) -> SyncProgress:
        """Sync all liked songs to local catalog."""
        progress = sync_jobs[job_id]
        progress.status = "syncing"
        progress.started_at = datetime.now(timezone.utc)

        try:
            # Get total count
            total = await self.get_liked_songs_count()
            progress.total_tracks = total

            offset = 0
            while offset < total:
                progress.current_offset = offset

                # Fetch page of liked songs
                data = await self.fetch_liked_songs_page(offset, self.BATCH_SIZE)
                items = data.get("items", [])

                if not items:
                    break

                # Extract track IDs for audio features batch request
                track_ids = [item["track"]["id"] for item in items if item.get("track")]

                # Fetch audio features for this batch
                audio_features = await self.fetch_audio_features_batch(track_ids)
                features_map = {f["id"]: f for f in audio_features if f}

                # Process each track
                for item in items:
                    spotify_track = item.get("track")
                    if not spotify_track:
                        progress.skipped_tracks += 1
                        continue

                    try:
                        features = features_map.get(spotify_track["id"], {})
                        result = await self._upsert_track(session, spotify_track, features)

                        if result == "new":
                            progress.new_tracks += 1
                        elif result == "updated":
                            progress.updated_tracks += 1
                        else:
                            progress.skipped_tracks += 1

                        progress.processed_tracks += 1

                    except Exception as e:
                        progress.failed_tracks += 1
                        print(f"Error processing track {spotify_track.get('name')}: {e}")

                # Commit batch
                await session.commit()

                offset += self.BATCH_SIZE

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)

            # Update token sync stats
            token.last_sync_at = datetime.now(timezone.utc)
            token.tracks_synced = progress.new_tracks + progress.updated_tracks
            await session.commit()

            progress.status = "completed"
            progress.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            progress.status = "failed"
            progress.error_message = str(e)
            progress.completed_at = datetime.now(timezone.utc)

        return progress

    async def _upsert_track(
        self,
        session: AsyncSession,
        spotify_track: dict,
        audio_features: dict,
    ) -> str:
        """Insert or update a track from Spotify data.

        Returns: "new", "updated", or "skipped"
        """
        spotify_id = spotify_track["id"]
        isrc = spotify_track.get("external_ids", {}).get("isrc")

        # Check if track already exists by Spotify ID or ISRC
        existing_track = None

        # First check by ISRC (most reliable)
        if isrc:
            stmt = select(Track).where(Track.isrc == isrc)
            result = await session.execute(stmt)
            existing_track = result.scalar_one_or_none()

        # Then check by Spotify ID in streaming_ids
        if not existing_track:
            stmt = select(Track).where(
                Track.streaming_ids["spotify"].astext == spotify_id
            )
            result = await session.execute(stmt)
            existing_track = result.scalar_one_or_none()

        # Parse artists
        artists = [artist["name"] for artist in spotify_track.get("artists", [])]

        # Convert key to Camelot notation
        key = None
        pitch_class = audio_features.get("key", -1)
        mode = audio_features.get("mode", -1)
        if pitch_class >= 0 and mode >= 0:
            key = self.PITCH_CLASS_TO_CAMELOT.get((pitch_class, mode))

        # Prepare track data
        track_data = {
            "title": spotify_track["name"],
            "artists": artists,
            "album": spotify_track.get("album", {}).get("name"),
            "isrc": isrc,
            "duration_ms": spotify_track.get("duration_ms"),
            "bpm": audio_features.get("tempo"),
            "key": key,
            "energy": audio_features.get("energy"),
            "danceability": audio_features.get("danceability"),
            "valence": audio_features.get("valence"),
            "acousticness": audio_features.get("acousticness"),
            "instrumentalness": audio_features.get("instrumentalness"),
            "speechiness": audio_features.get("speechiness"),
            "liveness": audio_features.get("liveness"),
            "loudness": audio_features.get("loudness"),
            "is_enriched": True,
        }

        if existing_track:
            # Update existing track with Spotify data
            for field, value in track_data.items():
                if value is not None:
                    # Don't overwrite existing non-null values except for enrichment fields
                    current_value = getattr(existing_track, field, None)
                    if current_value is None or field in [
                        "energy", "danceability", "valence", "acousticness",
                        "instrumentalness", "speechiness", "liveness", "loudness",
                        "is_enriched"
                    ]:
                        setattr(existing_track, field, value)

            # Update streaming IDs
            streaming_ids = existing_track.streaming_ids or {}
            streaming_ids["spotify"] = spotify_id
            existing_track.streaming_ids = streaming_ids

            return "updated"

        else:
            # Create new track
            new_track = Track(
                **track_data,
                streaming_ids={"spotify": spotify_id},
            )
            session.add(new_track)
            await session.flush()

            # Add source link
            source_link = SourceLink(
                track_id=new_track.id,
                source="spotify",
                external_id=spotify_id,
                uri=spotify_track.get("external_urls", {}).get("spotify"),
                is_primary=True,
            )
            session.add(source_link)

            return "new"


async def start_spotify_sync(
    session: AsyncSession,
    token: StreamingServiceToken,
) -> str:
    """Start a Spotify sync job.

    Returns the job ID.
    """
    job_id = str(uuid4())

    # Initialize progress
    sync_jobs[job_id] = SyncProgress(
        job_id=job_id,
        status="pending",
    )

    # Start sync in background
    service = SpotifySyncService(token.access_token)

    # Run sync (in production, use Celery or similar)
    asyncio.create_task(
        service.sync_liked_songs(session, token, job_id)
    )

    return job_id


def get_sync_progress(job_id: str) -> Optional[SyncProgress]:
    """Get progress for a sync job."""
    return sync_jobs.get(job_id)
