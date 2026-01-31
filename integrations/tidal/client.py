"""Tidal API client for metadata enrichment."""

from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class TidalTrack:
    """Track data from Tidal API."""

    tidal_id: str
    isrc: Optional[str] = None
    title: str = ""
    artists: list[str] = None
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    audio_quality: Optional[str] = None  # LOW, HIGH, LOSSLESS, HI_RES
    explicit: bool = False
    popularity: Optional[int] = None

    def __post_init__(self):
        if self.artists is None:
            self.artists = []


class TidalClient:
    """Client for Tidal API.

    Note: Tidal's official API is limited. This uses tidalapi library
    patterns for authenticated access.
    """

    BASE_URL = "https://api.tidal.com/v1"
    AUTH_URL = "https://auth.tidal.com/v1"

    def __init__(
        self,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        """Initialize the Tidal client.

        Args:
            access_token: OAuth access token.
            client_id: Tidal client ID.
            client_secret: Tidal client secret.
        """
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._http_client: Optional[httpx.AsyncClient] = None
        self._country_code = "US"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated request to the Tidal API."""
        if not self.access_token:
            raise ValueError("Access token required for Tidal API")

        client = await self._get_client()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"

        params = kwargs.pop("params", {})
        params["countryCode"] = self._country_code

        response = await client.request(
            method,
            f"{self.BASE_URL}{endpoint}",
            headers=headers,
            params=params,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def _parse_track(self, data: dict) -> TidalTrack:
        """Parse track data from API response."""
        artists = []
        for artist in data.get("artists", []):
            if isinstance(artist, dict):
                artists.append(artist.get("name", ""))
            elif isinstance(artist, str):
                artists.append(artist)

        return TidalTrack(
            tidal_id=str(data.get("id", "")),
            isrc=data.get("isrc"),
            title=data.get("title", ""),
            artists=artists,
            album=data.get("album", {}).get("title") if isinstance(data.get("album"), dict) else None,
            duration_ms=data.get("duration", 0) * 1000 if data.get("duration") else None,
            audio_quality=data.get("audioQuality"),
            explicit=data.get("explicit", False),
            popularity=data.get("popularity"),
        )

    async def search_track(
        self,
        title: str,
        artists: list[str],
        isrc: Optional[str] = None,
    ) -> Optional[dict]:
        """Search for a track on Tidal.

        Args:
            title: Track title.
            artists: List of artist names.
            isrc: ISRC code for exact matching.

        Returns:
            Track data if found.
        """
        # Try ISRC search first
        if isrc:
            try:
                data = await self._request(
                    "GET",
                    "/search",
                    params={"query": isrc, "types": "TRACKS", "limit": 1},
                )
                tracks = data.get("tracks", {}).get("items", [])
                if tracks:
                    track = self._parse_track(tracks[0])
                    return self._track_to_dict(track)
            except Exception:
                pass

        # Fall back to title/artist search
        artist_str = " ".join(artists)
        query = f"{title} {artist_str}"

        try:
            data = await self._request(
                "GET",
                "/search",
                params={"query": query, "types": "TRACKS", "limit": 10},
            )
            tracks = data.get("tracks", {}).get("items", [])

            if tracks:
                best_match = self._find_best_match(tracks, title, artists)
                if best_match:
                    track = self._parse_track(best_match)
                    return self._track_to_dict(track)

        except Exception as e:
            print(f"Tidal search error: {e}")

        return None

    def _find_best_match(
        self,
        tracks: list[dict],
        title: str,
        artists: list[str],
    ) -> Optional[dict]:
        """Find the best matching track from search results."""
        title_lower = title.lower()
        artists_lower = {a.lower() for a in artists}

        for track in tracks:
            track_title = track.get("title", "").lower()
            track_artists = set()
            for a in track.get("artists", []):
                if isinstance(a, dict):
                    track_artists.add(a.get("name", "").lower())
                elif isinstance(a, str):
                    track_artists.add(a.lower())

            if title_lower in track_title or track_title in title_lower:
                if artists_lower & track_artists:
                    return track

        return tracks[0] if tracks else None

    def _track_to_dict(self, track: TidalTrack) -> dict:
        """Convert TidalTrack to dictionary."""
        return {
            "id": track.tidal_id,
            "isrc": track.isrc,
            "title": track.title,
            "artists": track.artists,
            "album": track.album,
            "duration_ms": track.duration_ms,
            "audio_quality": track.audio_quality,
            "explicit": track.explicit,
            "popularity": track.popularity,
        }

    async def get_saved_tracks(self, limit: int = 100) -> list[dict]:
        """Get user's saved/favorite tracks.

        Args:
            limit: Number of tracks per page.

        Returns:
            List of track data.
        """
        tracks = []
        offset = 0

        while True:
            try:
                data = await self._request(
                    "GET",
                    "/users/me/favorites/tracks",
                    params={"limit": limit, "offset": offset},
                )

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    track_data = item.get("item", item)
                    track = self._parse_track(track_data)
                    tracks.append(self._track_to_dict(track))

                if len(items) < limit:
                    break

                offset += limit

            except Exception as e:
                print(f"Error fetching Tidal favorites: {e}")
                break

        return tracks

    async def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        """Get tracks from a Tidal playlist.

        Args:
            playlist_id: Tidal playlist UUID.

        Returns:
            List of track data.
        """
        tracks = []
        offset = 0
        limit = 100

        while True:
            try:
                data = await self._request(
                    "GET",
                    f"/playlists/{playlist_id}/items",
                    params={"limit": limit, "offset": offset},
                )

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    track_data = item.get("item", {})
                    if track_data.get("type") == "track" or "title" in track_data:
                        track = self._parse_track(track_data)
                        tracks.append(self._track_to_dict(track))

                if len(items) < limit:
                    break

                offset += limit

            except Exception as e:
                print(f"Error fetching Tidal playlist: {e}")
                break

        return tracks

    async def get_track_by_id(self, track_id: str) -> Optional[dict]:
        """Get a track by its Tidal ID.

        Args:
            track_id: Tidal track ID.

        Returns:
            Track data if found.
        """
        try:
            data = await self._request("GET", f"/tracks/{track_id}")
            track = self._parse_track(data)
            return self._track_to_dict(track)
        except Exception as e:
            print(f"Error fetching Tidal track: {e}")
            return None

    async def get_user_playlists(self) -> list[dict]:
        """Get user's playlists.

        Returns:
            List of playlist data.
        """
        playlists = []
        offset = 0
        limit = 50

        while True:
            try:
                data = await self._request(
                    "GET",
                    "/users/me/playlists",
                    params={"limit": limit, "offset": offset},
                )

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    playlists.append({
                        "id": item.get("uuid"),
                        "name": item.get("title"),
                        "description": item.get("description"),
                        "track_count": item.get("numberOfTracks", 0),
                        "duration_seconds": item.get("duration", 0),
                        "created": item.get("created"),
                        "last_updated": item.get("lastUpdated"),
                    })

                if len(items) < limit:
                    break

                offset += limit

            except Exception as e:
                print(f"Error fetching Tidal playlists: {e}")
                break

        return playlists
