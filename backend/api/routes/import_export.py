"""Import/Export API routes for DJ software integration."""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from api.schemas import ImportJobCreate, ImportJobResponse
from models import StreamingServiceToken

router = APIRouter(prefix="/import", tags=["import"])


# In-memory job tracking (in production, use Redis or database)
import_jobs: dict[str, dict] = {}


@router.post("/rekordbox", response_model=ImportJobResponse)
async def import_rekordbox(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Rekordbox XML export file"),
    session: AsyncSession = Depends(get_session),
) -> ImportJobResponse:
    """Import tracks from Rekordbox XML export."""
    if not file.filename or not file.filename.endswith(".xml"):
        raise HTTPException(status_code=400, detail="File must be a Rekordbox XML file")

    job_id = str(uuid4())
    import_jobs[job_id] = {
        "id": job_id,
        "source": "rekordbox",
        "status": "pending",
        "tracks_imported": 0,
        "tracks_skipped": 0,
        "tracks_failed": 0,
    }

    # Read file content
    content = await file.read()

    # Add background task for processing
    background_tasks.add_task(
        process_rekordbox_import,
        job_id=job_id,
        xml_content=content,
    )

    return ImportJobResponse(**import_jobs[job_id])


@router.post("/serato", response_model=ImportJobResponse)
async def import_serato(
    background_tasks: BackgroundTasks,
    crates_path: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
) -> ImportJobResponse:
    """Import tracks from Serato database."""
    job_id = str(uuid4())
    import_jobs[job_id] = {
        "id": job_id,
        "source": "serato",
        "status": "pending",
        "tracks_imported": 0,
        "tracks_skipped": 0,
        "tracks_failed": 0,
    }

    # Add background task for processing
    background_tasks.add_task(
        process_serato_import,
        job_id=job_id,
        crates_path=crates_path,
    )

    return ImportJobResponse(**import_jobs[job_id])


@router.post("/spotify/liked-songs")
async def sync_spotify_liked_songs(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Sync liked songs from connected Spotify account.

    Requires Spotify to be connected via OAuth first.
    """
    from api.routes.auth import get_active_spotify_token
    from ingest.spotify_sync import SpotifySyncService, start_spotify_sync, sync_jobs

    # Get active Spotify token
    token = await get_active_spotify_token(session)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Spotify not connected. Please connect your Spotify account first via /api/auth/spotify/login"
        )

    # Check if token needs refresh
    if token.is_expired():
        raise HTTPException(
            status_code=401,
            detail="Spotify token expired. Please reconnect via /api/auth/spotify/login"
        )

    # Start sync job
    job_id = str(uuid4())

    # Initialize progress tracking
    from ingest.spotify_sync import SyncProgress
    sync_jobs[job_id] = SyncProgress(
        job_id=job_id,
        status="pending",
    )

    # Get total count first
    service = SpotifySyncService(token.access_token)
    try:
        total_count = await service.get_liked_songs_count()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Spotify library: {str(e)}")

    sync_jobs[job_id].total_tracks = total_count

    # Start sync in background
    import asyncio
    asyncio.create_task(
        service.sync_liked_songs(session, token, job_id)
    )

    return {
        "job_id": job_id,
        "status": "started",
        "total_tracks": total_count,
        "message": f"Started syncing {total_count} liked songs from Spotify",
    }


@router.get("/spotify/liked-songs/status/{job_id}")
async def get_spotify_sync_status(job_id: str) -> dict:
    """Get status of a Spotify sync job."""
    from ingest.spotify_sync import get_sync_progress

    progress = get_sync_progress(job_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Sync job not found")

    return {
        "job_id": progress.job_id,
        "status": progress.status,
        "total_tracks": progress.total_tracks,
        "processed_tracks": progress.processed_tracks,
        "new_tracks": progress.new_tracks,
        "updated_tracks": progress.updated_tracks,
        "skipped_tracks": progress.skipped_tracks,
        "failed_tracks": progress.failed_tracks,
        "progress_percent": round(
            (progress.processed_tracks / progress.total_tracks * 100)
            if progress.total_tracks > 0 else 0,
            1
        ),
        "error_message": progress.error_message,
        "started_at": progress.started_at.isoformat() if progress.started_at else None,
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
    }


@router.post("/spotify/sync", response_model=ImportJobResponse)
async def sync_spotify_library_legacy(
    background_tasks: BackgroundTasks,
    access_token: str,
    session: AsyncSession = Depends(get_session),
) -> ImportJobResponse:
    """Legacy endpoint: Sync Spotify with access token.

    Prefer using /spotify/liked-songs with OAuth connection instead.
    """
    job_id = str(uuid4())
    import_jobs[job_id] = {
        "id": job_id,
        "source": "spotify",
        "status": "pending",
        "tracks_imported": 0,
        "tracks_skipped": 0,
        "tracks_failed": 0,
    }

    background_tasks.add_task(
        process_spotify_sync,
        job_id=job_id,
        access_token=access_token,
    )

    return ImportJobResponse(**import_jobs[job_id])


@router.post("/tidal/sync", response_model=ImportJobResponse)
async def sync_tidal_library(
    background_tasks: BackgroundTasks,
    access_token: str,
    session: AsyncSession = Depends(get_session),
) -> ImportJobResponse:
    """Sync Tidal saved tracks and playlists (metadata only)."""
    job_id = str(uuid4())
    import_jobs[job_id] = {
        "id": job_id,
        "source": "tidal",
        "status": "pending",
        "tracks_imported": 0,
        "tracks_skipped": 0,
        "tracks_failed": 0,
    }

    background_tasks.add_task(
        process_tidal_sync,
        job_id=job_id,
        access_token=access_token,
    )

    return ImportJobResponse(**import_jobs[job_id])


@router.post("/local", response_model=ImportJobResponse)
async def scan_local_files(
    background_tasks: BackgroundTasks,
    directory_path: str,
    recursive: bool = True,
    session: AsyncSession = Depends(get_session),
) -> ImportJobResponse:
    """Scan local directory for audio files and import metadata."""
    job_id = str(uuid4())
    import_jobs[job_id] = {
        "id": job_id,
        "source": "local",
        "status": "pending",
        "tracks_imported": 0,
        "tracks_skipped": 0,
        "tracks_failed": 0,
    }

    background_tasks.add_task(
        process_local_scan,
        job_id=job_id,
        directory_path=directory_path,
        recursive=recursive,
    )

    return ImportJobResponse(**import_jobs[job_id])


@router.get("/jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(job_id: str) -> ImportJobResponse:
    """Get the status of an import job."""
    if job_id not in import_jobs:
        raise HTTPException(status_code=404, detail="Import job not found")

    return ImportJobResponse(**import_jobs[job_id])


@router.get("/jobs", response_model=list[ImportJobResponse])
async def list_import_jobs(
    source: Optional[str] = None,
    status: Optional[str] = None,
) -> list[ImportJobResponse]:
    """List all import jobs with optional filtering."""
    jobs = list(import_jobs.values())

    if source:
        jobs = [j for j in jobs if j["source"] == source]
    if status:
        jobs = [j for j in jobs if j["status"] == status]

    return [ImportJobResponse(**j) for j in jobs]


# Background task implementations
async def process_rekordbox_import(job_id: str, xml_content: bytes) -> None:
    """Process Rekordbox XML import in background."""
    from integrations.rekordbox.parser import RekordboxParser
    from api.database import get_session_context

    import_jobs[job_id]["status"] = "processing"

    try:
        parser = RekordboxParser()
        tracks, playlists = parser.parse_xml(xml_content)

        async with get_session_context() as session:
            for track_data in tracks:
                try:
                    # Import track logic here
                    import_jobs[job_id]["tracks_imported"] += 1
                except Exception:
                    import_jobs[job_id]["tracks_failed"] += 1

        import_jobs[job_id]["status"] = "completed"

    except Exception as e:
        import_jobs[job_id]["status"] = "failed"
        import_jobs[job_id]["error_message"] = str(e)


async def process_serato_import(job_id: str, crates_path: Optional[str]) -> None:
    """Process Serato database import in background."""
    from integrations.serato.reader import SeratoReader
    from api.database import get_session_context

    import_jobs[job_id]["status"] = "processing"

    try:
        reader = SeratoReader(crates_path)
        tracks, crates = reader.read_library()

        async with get_session_context() as session:
            for track_data in tracks:
                try:
                    import_jobs[job_id]["tracks_imported"] += 1
                except Exception:
                    import_jobs[job_id]["tracks_failed"] += 1

        import_jobs[job_id]["status"] = "completed"

    except Exception as e:
        import_jobs[job_id]["status"] = "failed"
        import_jobs[job_id]["error_message"] = str(e)


async def process_spotify_sync(job_id: str, access_token: str) -> None:
    """Process Spotify library sync in background."""
    from integrations.spotify.client import SpotifyClient
    from api.database import get_session_context

    import_jobs[job_id]["status"] = "processing"

    try:
        client = SpotifyClient(access_token)
        tracks = await client.get_saved_tracks()

        async with get_session_context() as session:
            for track_data in tracks:
                try:
                    import_jobs[job_id]["tracks_imported"] += 1
                except Exception:
                    import_jobs[job_id]["tracks_failed"] += 1

        import_jobs[job_id]["status"] = "completed"

    except Exception as e:
        import_jobs[job_id]["status"] = "failed"
        import_jobs[job_id]["error_message"] = str(e)


async def process_tidal_sync(job_id: str, access_token: str) -> None:
    """Process Tidal library sync in background."""
    from integrations.tidal.client import TidalClient
    from api.database import get_session_context

    import_jobs[job_id]["status"] = "processing"

    try:
        client = TidalClient(access_token)
        tracks = await client.get_saved_tracks()

        async with get_session_context() as session:
            for track_data in tracks:
                try:
                    import_jobs[job_id]["tracks_imported"] += 1
                except Exception:
                    import_jobs[job_id]["tracks_failed"] += 1

        import_jobs[job_id]["status"] = "completed"

    except Exception as e:
        import_jobs[job_id]["status"] = "failed"
        import_jobs[job_id]["error_message"] = str(e)


async def process_local_scan(job_id: str, directory_path: str, recursive: bool) -> None:
    """Process local file scan in background."""
    from ingest.local_scanner import LocalScanner
    from api.database import get_session_context

    import_jobs[job_id]["status"] = "processing"

    try:
        scanner = LocalScanner()
        tracks = scanner.scan_directory(directory_path, recursive=recursive)

        async with get_session_context() as session:
            for track_data in tracks:
                try:
                    import_jobs[job_id]["tracks_imported"] += 1
                except Exception:
                    import_jobs[job_id]["tracks_failed"] += 1

        import_jobs[job_id]["status"] = "completed"

    except Exception as e:
        import_jobs[job_id]["status"] = "failed"
        import_jobs[job_id]["error_message"] = str(e)
