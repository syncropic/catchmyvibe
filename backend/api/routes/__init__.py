"""API route modules."""

from api.routes.tracks import router as tracks_router
from api.routes.playlists import router as playlists_router
from api.routes.sessions import router as sessions_router
from api.routes.import_export import router as import_router
from api.routes.analysis import router as analysis_router

__all__ = [
    "tracks_router",
    "playlists_router",
    "sessions_router",
    "import_router",
    "analysis_router",
]
