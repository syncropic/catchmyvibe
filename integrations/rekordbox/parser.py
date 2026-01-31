"""Rekordbox XML export parser."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import unquote


@dataclass
class RekordboxCuePoint:
    """Represents a cue point from Rekordbox."""

    position_ms: int
    name: Optional[str] = None
    color: Optional[str] = None
    cue_type: str = "cue"  # cue, loop, memory
    loop_end_ms: Optional[int] = None


@dataclass
class RekordboxTrack:
    """Represents a track from Rekordbox XML export."""

    # Identity
    track_id: str
    title: str
    artists: list[str] = field(default_factory=list)
    album: Optional[str] = None
    label: Optional[str] = None
    genre: Optional[str] = None
    release_year: Optional[int] = None

    # Audio properties
    bpm: Optional[float] = None
    key: Optional[str] = None
    duration_ms: Optional[int] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None

    # File info
    file_path: str = ""
    file_size: Optional[int] = None

    # DJ metadata
    rating: Optional[int] = None
    color: Optional[str] = None
    comment: Optional[str] = None
    date_added: Optional[str] = None
    play_count: int = 0

    # Cue points
    cue_points: list[RekordboxCuePoint] = field(default_factory=list)


@dataclass
class RekordboxPlaylist:
    """Represents a playlist/folder from Rekordbox."""

    name: str
    playlist_type: str  # "0" for folder, "1" for playlist
    track_ids: list[str] = field(default_factory=list)
    children: list["RekordboxPlaylist"] = field(default_factory=list)


class RekordboxParser:
    """Parser for Rekordbox XML export files."""

    # Rekordbox key notation to Camelot wheel mapping
    KEY_MAP = {
        "0": "1A",  # C major -> 8B
        "1": "8A",  # Db major -> 3B
        "2": "3B",  # D major -> 10B
        "3": "10A",  # Eb major -> 5B
        "4": "5B",  # E major -> 12B
        "5": "12A",  # F major -> 7B
        "6": "7B",  # Gb major -> 2B
        "7": "2A",  # G major -> 9B
        "8": "9B",  # Ab major -> 4B
        "9": "4A",  # A major -> 11B
        "10": "11B",  # Bb major -> 6B
        "11": "6A",  # B major -> 1B
        "12": "5A",  # C minor -> 5A
        "13": "12B",  # Db minor -> 12A
        "14": "7A",  # D minor -> 7A
        "15": "2B",  # Eb minor -> 2A
        "16": "9A",  # E minor -> 9A
        "17": "4B",  # F minor -> 4A
        "18": "11A",  # F# minor -> 11A
        "19": "6B",  # G minor -> 6A
        "20": "1B",  # Ab minor -> 1A
        "21": "8B",  # A minor -> 8A
        "22": "3A",  # Bb minor -> 3A
        "23": "10B",  # B minor -> 10A
    }

    # Color mappings from Rekordbox color indices
    COLOR_MAP = {
        "0": None,  # No color
        "1": "#E91E63",  # Pink
        "2": "#F44336",  # Red
        "3": "#FF9800",  # Orange
        "4": "#FFEB3B",  # Yellow
        "5": "#4CAF50",  # Green
        "6": "#00BCD4",  # Aqua
        "7": "#2196F3",  # Blue
        "8": "#9C27B0",  # Purple
    }

    def __init__(self) -> None:
        """Initialize the parser."""
        self.tracks: dict[str, RekordboxTrack] = {}
        self.playlists: list[RekordboxPlaylist] = []

    def parse_file(self, file_path: str | Path) -> tuple[list[RekordboxTrack], list[RekordboxPlaylist]]:
        """Parse a Rekordbox XML export file.

        Args:
            file_path: Path to the Rekordbox XML file.

        Returns:
            Tuple of (tracks, playlists).
        """
        with open(file_path, "rb") as f:
            return self.parse_xml(f.read())

    def parse_xml(self, xml_content: bytes) -> tuple[list[RekordboxTrack], list[RekordboxPlaylist]]:
        """Parse Rekordbox XML content.

        Args:
            xml_content: XML content as bytes.

        Returns:
            Tuple of (tracks, playlists).
        """
        self.tracks = {}
        self.playlists = []

        root = ET.fromstring(xml_content)

        # Parse collection (tracks)
        collection = root.find(".//COLLECTION")
        if collection is not None:
            for track_elem in collection.findall("TRACK"):
                track = self._parse_track(track_elem)
                if track:
                    self.tracks[track.track_id] = track

        # Parse playlists
        playlists_node = root.find(".//PLAYLISTS/NODE[@Type='0']")
        if playlists_node is not None:
            self.playlists = self._parse_playlist_node(playlists_node)

        return list(self.tracks.values()), self.playlists

    def _parse_track(self, elem: ET.Element) -> Optional[RekordboxTrack]:
        """Parse a single track element."""
        track_id = elem.get("TrackID")
        title = elem.get("Name")

        if not track_id or not title:
            return None

        # Parse artists (may be comma-separated)
        artist_str = elem.get("Artist", "")
        artists = [a.strip() for a in artist_str.split(",") if a.strip()]

        # Parse file path (URL-encoded)
        location = elem.get("Location", "")
        if location.startswith("file://localhost/"):
            file_path = unquote(location[17:])  # Remove prefix and decode
        elif location.startswith("file:///"):
            file_path = unquote(location[8:])
        else:
            file_path = unquote(location)

        # Parse BPM
        bpm_str = elem.get("AverageBpm")
        bpm = float(bpm_str) if bpm_str else None

        # Parse key and convert to Camelot notation
        tonality = elem.get("Tonality", "")
        key = self._convert_key(tonality)

        # Parse duration (stored in seconds with decimals)
        total_time = elem.get("TotalTime")
        duration_ms = int(float(total_time) * 1000) if total_time else None

        # Parse rating (0-255 scale, convert to 1-5)
        rating_str = elem.get("Rating")
        rating = None
        if rating_str:
            rating_val = int(rating_str)
            if rating_val > 0:
                rating = min(5, max(1, rating_val // 51 + 1))

        # Parse year
        year_str = elem.get("Year")
        year = int(year_str) if year_str and year_str.isdigit() else None

        # Parse play count
        play_count_str = elem.get("PlayCount", "0")
        play_count = int(play_count_str) if play_count_str.isdigit() else 0

        # Parse color
        color_idx = elem.get("Colour")
        color = self.COLOR_MAP.get(color_idx) if color_idx else None

        track = RekordboxTrack(
            track_id=track_id,
            title=title,
            artists=artists,
            album=elem.get("Album"),
            label=elem.get("Label"),
            genre=elem.get("Genre"),
            release_year=year,
            bpm=bpm,
            key=key,
            duration_ms=duration_ms,
            bitrate=int(elem.get("BitRate", "0")) or None,
            sample_rate=int(elem.get("SampleRate", "0")) or None,
            file_path=file_path,
            file_size=int(elem.get("Size", "0")) or None,
            rating=rating,
            color=color,
            comment=elem.get("Comments"),
            date_added=elem.get("DateAdded"),
            play_count=play_count,
        )

        # Parse cue points
        for cue_elem in elem.findall(".//POSITION_MARK") + elem.findall(".//TEMPO"):
            cue = self._parse_cue_point(cue_elem)
            if cue:
                track.cue_points.append(cue)

        return track

    def _parse_cue_point(self, elem: ET.Element) -> Optional[RekordboxCuePoint]:
        """Parse a cue point or position mark."""
        if elem.tag == "POSITION_MARK":
            # Memory cue or hot cue
            start = elem.get("Start")
            if not start:
                return None

            position_ms = int(float(start) * 1000)

            # Determine cue type
            cue_type_num = elem.get("Type", "0")
            if cue_type_num == "0":
                cue_type = "cue"
            elif cue_type_num == "4":
                cue_type = "loop"
            else:
                cue_type = "memory"

            # Parse loop end if it's a loop
            loop_end_ms = None
            if cue_type == "loop":
                end = elem.get("End")
                if end:
                    loop_end_ms = int(float(end) * 1000)

            # Parse color
            color_idx = elem.get("Red")
            if color_idx:
                # Rekordbox uses RGB values
                red = int(elem.get("Red", "0"))
                green = int(elem.get("Green", "0"))
                blue = int(elem.get("Blue", "0"))
                color = f"#{red:02X}{green:02X}{blue:02X}"
            else:
                color = None

            return RekordboxCuePoint(
                position_ms=position_ms,
                name=elem.get("Name"),
                color=color,
                cue_type=cue_type,
                loop_end_ms=loop_end_ms,
            )

        return None

    def _parse_playlist_node(self, node: ET.Element) -> list[RekordboxPlaylist]:
        """Recursively parse playlist nodes."""
        playlists = []

        for child in node.findall("NODE"):
            node_type = child.get("Type", "0")
            name = child.get("Name", "Unnamed")

            if node_type == "0":
                # Folder
                playlist = RekordboxPlaylist(
                    name=name,
                    playlist_type="folder",
                    children=self._parse_playlist_node(child),
                )
            else:
                # Playlist
                track_ids = []
                for track_elem in child.findall("TRACK"):
                    key = track_elem.get("Key")
                    if key:
                        track_ids.append(key)

                playlist = RekordboxPlaylist(
                    name=name,
                    playlist_type="playlist",
                    track_ids=track_ids,
                )

            playlists.append(playlist)

        return playlists

    def _convert_key(self, tonality: str) -> Optional[str]:
        """Convert Rekordbox key notation to Camelot wheel notation."""
        if not tonality:
            return None

        # Rekordbox stores key as number (0-23)
        if tonality.isdigit():
            return self.KEY_MAP.get(tonality)

        # Some versions use text format (e.g., "Dm", "F#m")
        # Convert to Camelot wheel
        key_to_camelot = {
            "C": "8B", "Cm": "5A",
            "Db": "3B", "C#": "3B", "Dbm": "12A", "C#m": "12A",
            "D": "10B", "Dm": "7A",
            "Eb": "5B", "D#": "5B", "Ebm": "2A", "D#m": "2A",
            "E": "12B", "Em": "9A",
            "F": "7B", "Fm": "4A",
            "Gb": "2B", "F#": "2B", "Gbm": "11A", "F#m": "11A",
            "G": "9B", "Gm": "6A",
            "Ab": "4B", "G#": "4B", "Abm": "1A", "G#m": "1A",
            "A": "11B", "Am": "8A",
            "Bb": "6B", "A#": "6B", "Bbm": "3A", "A#m": "3A",
            "B": "1B", "Bm": "10A",
        }

        return key_to_camelot.get(tonality)

    def get_track_by_id(self, track_id: str) -> Optional[RekordboxTrack]:
        """Get a track by its Rekordbox ID."""
        return self.tracks.get(track_id)
