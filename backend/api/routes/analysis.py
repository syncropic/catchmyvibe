"""Analysis and enrichment API routes."""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.schemas import (
    AnalysisJobCreate,
    AnalysisJobResponse,
    EnrichmentJobCreate,
    EnrichmentJobResponse,
)
from models import Track

router = APIRouter(prefix="/analysis", tags=["analysis"])


# In-memory job tracking (in production, use Celery/Redis)
analysis_jobs: dict[str, dict] = {}
enrichment_jobs: dict[str, dict] = {}


@router.post("/analyze", response_model=AnalysisJobResponse)
async def queue_analysis(
    request: AnalysisJobCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> AnalysisJobResponse:
    """Queue tracks for deep audio analysis."""
    # Verify tracks exist
    stmt = select(Track).where(Track.id.in_(request.track_ids))
    result = await session.execute(stmt)
    tracks = result.scalars().all()

    if len(tracks) != len(request.track_ids):
        found_ids = {t.id for t in tracks}
        missing = [tid for tid in request.track_ids if tid not in found_ids]
        raise HTTPException(
            status_code=404,
            detail=f"Tracks not found: {missing}",
        )

    # Filter to tracks that need analysis (unless force=True)
    tracks_to_analyze = tracks
    if not request.force:
        tracks_to_analyze = [t for t in tracks if not t.is_analyzed]

    if not tracks_to_analyze:
        return AnalysisJobResponse(
            job_id="",
            tracks_queued=0,
            message="All tracks already analyzed",
        )

    job_id = str(uuid4())
    analysis_jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "track_ids": [t.id for t in tracks_to_analyze],
        "completed": 0,
        "failed": 0,
    }

    background_tasks.add_task(
        process_analysis_job,
        job_id=job_id,
        track_ids=[t.id for t in tracks_to_analyze],
    )

    return AnalysisJobResponse(
        job_id=job_id,
        tracks_queued=len(tracks_to_analyze),
        message=f"Queued {len(tracks_to_analyze)} tracks for analysis",
    )


@router.post("/enrich", response_model=EnrichmentJobResponse)
async def queue_enrichment(
    request: EnrichmentJobCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> EnrichmentJobResponse:
    """Queue tracks for API enrichment (Spotify/Tidal metadata)."""
    if request.track_ids:
        # Specific tracks
        stmt = select(Track).where(Track.id.in_(request.track_ids))
    else:
        # All un-enriched tracks
        stmt = select(Track).where(Track.is_enriched == False).limit(1000)  # noqa: E712

    result = await session.execute(stmt)
    tracks = result.scalars().all()

    if not tracks:
        return EnrichmentJobResponse(
            job_id="",
            tracks_queued=0,
            message="No tracks to enrich",
        )

    job_id = str(uuid4())
    enrichment_jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "track_ids": [t.id for t in tracks],
        "completed": 0,
        "failed": 0,
    }

    background_tasks.add_task(
        process_enrichment_job,
        job_id=job_id,
        track_ids=[t.id for t in tracks],
    )

    return EnrichmentJobResponse(
        job_id=job_id,
        tracks_queued=len(tracks),
        message=f"Queued {len(tracks)} tracks for enrichment",
    )


@router.get("/jobs/{job_id}")
async def get_analysis_job(job_id: str) -> dict:
    """Get the status of an analysis or enrichment job."""
    if job_id in analysis_jobs:
        return {"type": "analysis", **analysis_jobs[job_id]}
    if job_id in enrichment_jobs:
        return {"type": "enrichment", **enrichment_jobs[job_id]}

    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/stats")
async def get_analysis_stats(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get analysis statistics for the catalog."""
    from sqlalchemy import func

    # Total tracks
    total_stmt = select(func.count(Track.id))
    total = (await session.execute(total_stmt)).scalar() or 0

    # Analyzed tracks
    analyzed_stmt = select(func.count(Track.id)).where(Track.is_analyzed == True)  # noqa: E712
    analyzed = (await session.execute(analyzed_stmt)).scalar() or 0

    # Enriched tracks
    enriched_stmt = select(func.count(Track.id)).where(Track.is_enriched == True)  # noqa: E712
    enriched = (await session.execute(enriched_stmt)).scalar() or 0

    # Tracks with embeddings
    embeddings_stmt = select(func.count(Track.id)).where(Track.embedding.isnot(None))
    with_embeddings = (await session.execute(embeddings_stmt)).scalar() or 0

    return {
        "total_tracks": total,
        "analyzed_tracks": analyzed,
        "enriched_tracks": enriched,
        "tracks_with_embeddings": with_embeddings,
        "analysis_percentage": round(analyzed / total * 100, 1) if total > 0 else 0,
        "enrichment_percentage": round(enriched / total * 100, 1) if total > 0 else 0,
    }


# Background task implementations
async def process_analysis_job(job_id: str, track_ids: list[str]) -> None:
    """Process audio analysis in background."""
    from analysis.audio_analyzer import AudioAnalyzer
    from api.database import get_session_context

    analysis_jobs[job_id]["status"] = "processing"

    analyzer = AudioAnalyzer()

    async with get_session_context() as session:
        for track_id in track_ids:
            try:
                # Get track
                stmt = select(Track).where(Track.id == track_id)
                result = await session.execute(stmt)
                track = result.scalar_one_or_none()

                if not track or not track.cloud_uri:
                    analysis_jobs[job_id]["failed"] += 1
                    continue

                # Analyze
                analysis_result = await analyzer.analyze_track(track.cloud_uri)

                # Update track with results
                track.bpm = analysis_result.get("bpm", track.bpm)
                track.key = analysis_result.get("key", track.key)
                track.energy = analysis_result.get("energy")
                track.embedding = analysis_result.get("embedding")
                track.waveform_data = analysis_result.get("waveform")
                track.is_analyzed = True

                analysis_jobs[job_id]["completed"] += 1

            except Exception as e:
                analysis_jobs[job_id]["failed"] += 1
                # Log error
                print(f"Analysis failed for track {track_id}: {e}")

        await session.commit()

    analysis_jobs[job_id]["status"] = "completed"


async def process_enrichment_job(job_id: str, track_ids: list[str]) -> None:
    """Process API enrichment in background."""
    from integrations.spotify.client import SpotifyClient
    from api.database import get_session_context
    from api.config import get_settings

    settings = get_settings()
    enrichment_jobs[job_id]["status"] = "processing"

    async with get_session_context() as session:
        for track_id in track_ids:
            try:
                # Get track
                stmt = select(Track).where(Track.id == track_id)
                result = await session.execute(stmt)
                track = result.scalar_one_or_none()

                if not track:
                    enrichment_jobs[job_id]["failed"] += 1
                    continue

                # Try to match with Spotify
                if settings.spotify_client_id and settings.spotify_client_secret:
                    client = SpotifyClient()
                    spotify_data = await client.search_track(
                        title=track.title,
                        artists=track.artists,
                        isrc=track.isrc,
                    )

                    if spotify_data:
                        # Update track with Spotify features
                        track.streaming_ids = {
                            **track.streaming_ids,
                            "spotify": spotify_data.get("id"),
                        }
                        track.isrc = spotify_data.get("isrc") or track.isrc
                        track.energy = spotify_data.get("energy", track.energy)
                        track.danceability = spotify_data.get("danceability", track.danceability)
                        track.valence = spotify_data.get("valence", track.valence)
                        track.acousticness = spotify_data.get("acousticness", track.acousticness)
                        track.instrumentalness = spotify_data.get("instrumentalness", track.instrumentalness)
                        track.speechiness = spotify_data.get("speechiness", track.speechiness)
                        track.liveness = spotify_data.get("liveness", track.liveness)
                        track.loudness = spotify_data.get("loudness", track.loudness)

                track.is_enriched = True
                enrichment_jobs[job_id]["completed"] += 1

            except Exception as e:
                enrichment_jobs[job_id]["failed"] += 1
                print(f"Enrichment failed for track {track_id}: {e}")

        await session.commit()

    enrichment_jobs[job_id]["status"] = "completed"
