"""Spotify API client for metadata enrichment."""

import base64
from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class SpotifyTrackFeatures:
    """Audio features from Spotify API."""

    spotify_id: str
    isrc: Optional[str] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    mode: Optional[str] = None  # major/minor
    energy: Optional[float] = None
    danceability: Optional[float] = None
    valence: Optional[float] = None
    acousticness: Optional[float] = None
    instrumentalness: Optional[float] = None
    speechiness: Optional[float] = None
    liveness: Optional[float] = None
    loudness: Optional[float] = None
    duration_ms: Optional[int] = None
    time_signature: Optional[int] = None
    popularity: Optional[int] = None


class SpotifyClient:
    """Client for Spotify Web API."""

    BASE_URL = "https://api.spotify.com/v1"
    AUTH_URL = "https://accounts.spotify.com/api/token"

    # Spotify key notation to Camelot wheel
    PITCH_CLASS_TO_CAMELOT = {
        # Major keys (mode = 1)
        (0, 1): "8B",   # C major
        (1, 1): "3B",   # C#/Db major
        (2, 1): "10B",  # D major
        (3, 1): "5B",   # D#/Eb major
        (4, 1): "12B",  # E major
        (5, 1): "7B",   # F major
        (6, 1): "2B",   # F#/Gb major
        (7, 1): "9B",   # G major
        (8, 1): "4B",   # G#/Ab major
        (9, 1): "11B",  # A major
        (10, 1): "6B",  # A#/Bb major
        (11, 1): "1B",  # B major
        # Minor keys (mode = 0)
        (0, 0): "5A",   # C minor
        (1, 0): "12A",  # C#/Db minor
        (2, 0): "7A",   # D minor
        (3, 0): "2A",   # D#/Eb minor
        (4, 0): "9A",   # E minor
        (5, 0): "4A",   # F minor
        (6, 0): "11A",  # F#/Gb minor
        (7, 0): "6A",   # G minor
        (8, 0): "1A",   # G#/Ab minor
        (9, 0): "8A",   # A minor
        (10, 0): "3A",  # A#/Bb minor
        (11, 0): "10A", # B minor
    }

    def __init__(
        self,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        """Initialize the Spotify client.

        Args:
            access_token: OAuth access token for user-level access.
            client_id: Spotify client ID for client credentials flow.
            client_secret: Spotify client secret for client credentials flow.
        """
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    async def _ensure_token(self) -> str:
        """Ensure we have a valid access token."""
        if self.access_token:
            return self.access_token

        if self.client_id and self.client_secret:
            return await self._get_client_credentials_token()

        raise ValueError("No access token or client credentials provided")

    async def _get_client_credentials_token(self) -> str:
        """Get access token using client credentials flow."""
        client = await self._get_client()

        auth_str = f"{self.client_id}:{self.client_secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()

        response = await client.post(
            self.AUTH_URL,
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()

        data = response.json()
        self.access_token = data["access_token"]
        return self.access_token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated request to the Spotify API."""
        token = await self._ensure_token()
        client = await self._get_client()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        response = await client.request(
            method,
            f"{self.BASE_URL}{endpoint}",
            headers=headers,
            **kwargs,
        )

        if response.status_code == 429:
            # Rate limited, let tenacity retry
            retry_after = int(response.headers.get("Retry-After", 1))
            import asyncio
            await asyncio.sleep(retry_after)
            response.raise_for_status()

        response.raise_for_status()
        return response.json()

    async def search_track(
        self,
        title: str,
        artists: list[str],
        isrc: Optional[str] = None,
    ) -> Optional[dict]:
        """Search for a track on Spotify.

        Args:
            title: Track title.
            artists: List of artist names.
            isrc: ISRC code for exact matching.

        Returns:
            Track data with audio features if found.
        """
        # Try ISRC search first (most accurate)
        if isrc:
            try:
                data = await self._request("GET", "/search", params={
                    "q": f"isrc:{isrc}",
                    "type": "track",
                    "limit": 1,
                })
                tracks = data.get("tracks", {}).get("items", [])
                if tracks:
                    return await self._get_track_with_features(tracks[0])
            except Exception:
                pass

        # Fall back to title/artist search
        artist_str = " ".join(artists)
        query = f"track:{title} artist:{artist_str}"

        try:
            data = await self._request("GET", "/search", params={
                "q": query,
                "type": "track",
                "limit": 5,
            })
            tracks = data.get("tracks", {}).get("items", [])

            if not tracks:
                # Try simpler query
                data = await self._request("GET", "/search", params={
                    "q": f"{title} {artist_str}",
                    "type": "track",
                    "limit": 5,
                })
                tracks = data.get("tracks", {}).get("items", [])

            if tracks:
                # Find best match
                best_match = self._find_best_match(tracks, title, artists)
                if best_match:
                    return await self._get_track_with_features(best_match)

        except Exception as e:
            print(f"Spotify search error: {e}")

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
            track_title = track.get("name", "").lower()
            track_artists = {a.get("name", "").lower() for a in track.get("artists", [])}

            # Check title similarity
            if title_lower in track_title or track_title in title_lower:
                # Check artist overlap
                if artists_lower & track_artists:
                    return track

        # Return first result as fallback
        return tracks[0] if tracks else None

    async def _get_track_with_features(self, track: dict) -> dict:
        """Get track data enriched with audio features."""
        track_id = track["id"]

        # Get audio features
        try:
            features = await self._request("GET", f"/audio-features/{track_id}")
        except Exception:
            features = {}

        # Get ISRC from track info
        isrc = None
        external_ids = track.get("external_ids", {})
        if external_ids:
            isrc = external_ids.get("isrc")

        # Convert key/mode to Camelot notation
        key = None
        pitch_class = features.get("key", -1)
        mode = features.get("mode", -1)
        if pitch_class >= 0 and mode >= 0:
            key = self.PITCH_CLASS_TO_CAMELOT.get((pitch_class, mode))

        return {
            "id": track_id,
            "isrc": isrc,
            "name": track.get("name"),
            "artists": [a.get("name") for a in track.get("artists", [])],
            "album": track.get("album", {}).get("name"),
            "duration_ms": track.get("duration_ms"),
            "popularity": track.get("popularity"),
            "preview_url": track.get("preview_url"),
            "external_url": track.get("external_urls", {}).get("spotify"),
            # Audio features
            "bpm": features.get("tempo"),
            "key": key,
            "energy": features.get("energy"),
            "danceability": features.get("danceability"),
            "valence": features.get("valence"),
            "acousticness": features.get("acousticness"),
            "instrumentalness": features.get("instrumentalness"),
            "speechiness": features.get("speechiness"),
            "liveness": features.get("liveness"),
            "loudness": features.get("loudness"),
            "time_signature": features.get("time_signature"),
        }

    async def get_saved_tracks(self, limit: int = 50) -> list[dict]:
        """Get user's saved tracks (requires user OAuth token).

        Args:
            limit: Number of tracks per page (max 50).

        Returns:
            List of track data with audio features.
        """
        tracks = []
        offset = 0

        while True:
            data = await self._request(
                "GET",
                "/me/tracks",
                params={"limit": limit, "offset": offset},
            )

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                track = item.get("track")
                if track:
                    enriched = await self._get_track_with_features(track)
                    tracks.append(enriched)

            if not data.get("next"):
                break

            offset += limit

        return tracks

    async def get_playlist_tracks(self, playlist_id: str) -> list[dict]:
        """Get tracks from a playlist.

        Args:
            playlist_id: Spotify playlist ID.

        Returns:
            List of track data with audio features.
        """
        tracks = []
        offset = 0
        limit = 100

        while True:
            data = await self._request(
                "GET",
                f"/playlists/{playlist_id}/tracks",
                params={"limit": limit, "offset": offset},
            )

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                track = item.get("track")
                if track and track.get("id"):  # Skip local files
                    enriched = await self._get_track_with_features(track)
                    tracks.append(enriched)

            if not data.get("next"):
                break

            offset += limit

        return tracks

    async def get_audio_features_batch(self, track_ids: list[str]) -> list[dict]:
        """Get audio features for multiple tracks at once.

        Args:
            track_ids: List of Spotify track IDs (max 100).

        Returns:
            List of audio features.
        """
        if not track_ids:
            return []

        # API allows max 100 tracks per request
        track_ids = track_ids[:100]

        data = await self._request(
            "GET",
            "/audio-features",
            params={"ids": ",".join(track_ids)},
        )

        features_list = []
        for features in data.get("audio_features", []):
            if features:
                pitch_class = features.get("key", -1)
                mode = features.get("mode", -1)
                key = None
                if pitch_class >= 0 and mode >= 0:
                    key = self.PITCH_CLASS_TO_CAMELOT.get((pitch_class, mode))

                features_list.append({
                    "id": features.get("id"),
                    "bpm": features.get("tempo"),
                    "key": key,
                    "energy": features.get("energy"),
                    "danceability": features.get("danceability"),
                    "valence": features.get("valence"),
                    "acousticness": features.get("acousticness"),
                    "instrumentalness": features.get("instrumentalness"),
                    "speechiness": features.get("speechiness"),
                    "liveness": features.get("liveness"),
                    "loudness": features.get("loudness"),
                    "time_signature": features.get("time_signature"),
                    "duration_ms": features.get("duration_ms"),
                })

        return features_list
