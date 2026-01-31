"""Serato database and crate reader."""

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mutagen import File as MutagenFile
from mutagen.id3 import ID3


@dataclass
class SeratoCuePoint:
    """Represents a cue point from Serato."""

    position_ms: int
    name: Optional[str] = None
    color: Optional[str] = None
    cue_type: str = "cue"  # cue, loop
    loop_end_ms: Optional[int] = None


@dataclass
class SeratoTrack:
    """Represents a track from Serato."""

    # Identity
    file_path: str
    title: str
    artists: list[str] = field(default_factory=list)
    album: Optional[str] = None
    genre: Optional[str] = None
    release_year: Optional[int] = None

    # Audio properties
    bpm: Optional[float] = None
    key: Optional[str] = None
    duration_ms: Optional[int] = None

    # Metadata
    comment: Optional[str] = None
    rating: Optional[int] = None

    # Cue points
    cue_points: list[SeratoCuePoint] = field(default_factory=list)


@dataclass
class SeratoCrate:
    """Represents a Serato crate."""

    name: str
    file_paths: list[str] = field(default_factory=list)
    parent: Optional[str] = None


class SeratoReader:
    """Reader for Serato database and crates."""

    # Default Serato database locations
    SERATO_PATHS = {
        "darwin": Path.home() / "Music" / "_Serato_",
        "linux": Path.home() / "Music" / "_Serato_",
        "win32": Path.home() / "Music" / "_Serato_",
    }

    # Serato key notation
    KEY_MAP = {
        "1m": "5A", "1d": "5B",
        "2m": "12A", "2d": "12B",
        "3m": "7A", "3d": "7B",
        "4m": "2A", "4d": "2B",
        "5m": "9A", "5d": "9B",
        "6m": "4A", "6d": "4B",
        "7m": "11A", "7d": "11B",
        "8m": "6A", "8d": "6B",
        "9m": "1A", "9d": "1B",
        "10m": "8A", "10d": "8B",
        "11m": "3A", "11d": "3B",
        "12m": "10A", "12d": "10B",
    }

    def __init__(self, serato_path: Optional[str] = None) -> None:
        """Initialize the Serato reader.

        Args:
            serato_path: Optional custom path to Serato folder.
        """
        if serato_path:
            self.serato_path = Path(serato_path)
        else:
            import sys
            self.serato_path = self.SERATO_PATHS.get(sys.platform, self.SERATO_PATHS["linux"])

    def read_library(self) -> tuple[list[SeratoTrack], list[SeratoCrate]]:
        """Read the Serato library.

        Returns:
            Tuple of (tracks, crates).
        """
        tracks = []
        crates = self.read_crates()

        # Collect unique file paths from all crates
        all_paths: set[str] = set()
        for crate in crates:
            all_paths.update(crate.file_paths)

        # Read track metadata
        for file_path in all_paths:
            track = self.read_track(file_path)
            if track:
                tracks.append(track)

        return tracks, crates

    def read_crates(self) -> list[SeratoCrate]:
        """Read all Serato crates.

        Returns:
            List of crates.
        """
        crates = []
        crates_path = self.serato_path / "Subcrates"

        if not crates_path.exists():
            return crates

        for crate_file in crates_path.glob("*.crate"):
            try:
                crate = self._parse_crate_file(crate_file)
                if crate:
                    crates.append(crate)
            except Exception as e:
                print(f"Error reading crate {crate_file}: {e}")

        return crates

    def _parse_crate_file(self, crate_path: Path) -> Optional[SeratoCrate]:
        """Parse a Serato crate file.

        Serato crate files have a custom binary format with header tags.
        """
        with open(crate_path, "rb") as f:
            content = f.read()

        # Crate name from filename (remove .crate extension)
        name = crate_path.stem

        # Handle subcrate naming (e.g., "ParentCrate%%SubCrate")
        parent = None
        if "%%" in name:
            parts = name.rsplit("%%", 1)
            parent = parts[0].replace("%%", "/")
            name = parts[1]

        file_paths = []

        # Parse crate content
        # Serato uses a tag-based format: [tag][size][data]
        pos = 0
        while pos < len(content) - 8:
            # Read tag (4 bytes)
            tag = content[pos : pos + 4].decode("ascii", errors="ignore")
            pos += 4

            # Read size (4 bytes, big endian)
            size = struct.unpack(">I", content[pos : pos + 4])[0]
            pos += 4

            # Read data
            data = content[pos : pos + size]
            pos += size

            if tag == "otrk":
                # Track path entry
                try:
                    # Path is stored as null-terminated UTF-16
                    path = data.decode("utf-16-be").rstrip("\x00")
                    if path.startswith("ptrk"):
                        path = path[4:]  # Remove 'ptrk' prefix if present
                    file_paths.append(path)
                except Exception:
                    pass

        return SeratoCrate(name=name, file_paths=file_paths, parent=parent)

    def read_track(self, file_path: str) -> Optional[SeratoTrack]:
        """Read track metadata including Serato-specific data.

        Args:
            file_path: Path to the audio file.

        Returns:
            SeratoTrack or None if file can't be read.
        """
        if not os.path.exists(file_path):
            return None

        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return None

            # Extract basic metadata
            title = self._get_tag(audio, ["title", "TIT2", "\xa9nam"]) or Path(file_path).stem
            artist = self._get_tag(audio, ["artist", "TPE1", "\xa9ART"]) or ""
            artists = [a.strip() for a in artist.split(",") if a.strip()]
            album = self._get_tag(audio, ["album", "TALB", "\xa9alb"])
            genre = self._get_tag(audio, ["genre", "TCON", "\xa9gen"])

            # Get BPM
            bpm_str = self._get_tag(audio, ["bpm", "TBPM"])
            bpm = float(bpm_str) if bpm_str else None

            # Duration
            duration_ms = int(audio.info.length * 1000) if hasattr(audio.info, "length") else None

            # Get year
            year_str = self._get_tag(audio, ["date", "TDRC", "\xa9day"])
            year = None
            if year_str:
                try:
                    year = int(year_str[:4])
                except ValueError:
                    pass

            track = SeratoTrack(
                file_path=file_path,
                title=title,
                artists=artists,
                album=album,
                genre=genre,
                release_year=year,
                bpm=bpm,
                duration_ms=duration_ms,
            )

            # Try to read Serato-specific data from ID3 GEOB frames
            if hasattr(audio, "tags") and audio.tags:
                track.cue_points = self._read_serato_markers(audio.tags)
                key = self._read_serato_key(audio.tags)
                if key:
                    track.key = key

            return track

        except Exception as e:
            print(f"Error reading track {file_path}: {e}")
            return None

    def _get_tag(self, audio: MutagenFile, tag_names: list[str]) -> Optional[str]:
        """Get a tag value from various possible tag names."""
        if not hasattr(audio, "tags") or audio.tags is None:
            return None

        for name in tag_names:
            value = audio.tags.get(name)
            if value:
                if isinstance(value, list):
                    return str(value[0])
                return str(value)

        return None

    def _read_serato_markers(self, tags: ID3) -> list[SeratoCuePoint]:
        """Read Serato cue points from ID3 GEOB frames."""
        cues = []

        # Serato stores markers in GEOB frames with specific descriptions
        for key in tags.keys():
            if key.startswith("GEOB:Serato Markers2"):
                try:
                    geob = tags[key]
                    cues.extend(self._parse_serato_markers2(geob.data))
                except Exception:
                    pass

        return cues

    def _parse_serato_markers2(self, data: bytes) -> list[SeratoCuePoint]:
        """Parse Serato Markers2 binary format."""
        cues = []

        # Skip header
        if len(data) < 2:
            return cues

        pos = 2
        while pos < len(data) - 10:
            try:
                # Entry type (1 byte)
                entry_type = data[pos]
                pos += 1

                # Entry length (4 bytes, big endian)
                entry_len = struct.unpack(">I", data[pos : pos + 4])[0]
                pos += 4

                entry_data = data[pos : pos + entry_len]
                pos += entry_len

                if entry_type == 0x00:
                    # Cue point
                    if len(entry_data) >= 13:
                        # Position in ms (4 bytes)
                        position_ms = struct.unpack(">I", entry_data[1:5])[0]
                        # Color RGB (3 bytes)
                        r, g, b = entry_data[5], entry_data[6], entry_data[7]
                        color = f"#{r:02X}{g:02X}{b:02X}"

                        cues.append(
                            SeratoCuePoint(
                                position_ms=position_ms,
                                color=color,
                                cue_type="cue",
                            )
                        )

                elif entry_type == 0x03:
                    # Loop
                    if len(entry_data) >= 17:
                        start_ms = struct.unpack(">I", entry_data[1:5])[0]
                        end_ms = struct.unpack(">I", entry_data[5:9])[0]
                        r, g, b = entry_data[13], entry_data[14], entry_data[15]
                        color = f"#{r:02X}{g:02X}{b:02X}"

                        cues.append(
                            SeratoCuePoint(
                                position_ms=start_ms,
                                color=color,
                                cue_type="loop",
                                loop_end_ms=end_ms,
                            )
                        )

            except Exception:
                break

        return cues

    def _read_serato_key(self, tags: ID3) -> Optional[str]:
        """Read Serato key from ID3 tags."""
        # Check TKEY (standard key tag)
        if "TKEY" in tags:
            key_str = str(tags["TKEY"])
            return self._convert_key(key_str)

        # Check Serato-specific key tag
        for key in tags.keys():
            if key.startswith("GEOB:Serato AutoTags"):
                try:
                    geob = tags[key]
                    # Parse key from autotags data
                    data = geob.data.decode("utf-8", errors="ignore")
                    if "KEY" in data:
                        # Extract key value
                        parts = data.split("\x00")
                        for i, part in enumerate(parts):
                            if "KEY" in part and i + 1 < len(parts):
                                return self._convert_key(parts[i + 1])
                except Exception:
                    pass

        return None

    def _convert_key(self, key_str: str) -> Optional[str]:
        """Convert various key formats to Camelot notation."""
        if not key_str:
            return None

        key_str = key_str.strip().lower()

        # Already in Serato format (e.g., "1m", "5d")
        if key_str in self.KEY_MAP:
            return self.KEY_MAP[key_str]

        # Musical notation (e.g., "Am", "C")
        key_to_camelot = {
            "c": "8B", "cm": "5A",
            "db": "3B", "c#": "3B", "dbm": "12A", "c#m": "12A",
            "d": "10B", "dm": "7A",
            "eb": "5B", "d#": "5B", "ebm": "2A", "d#m": "2A",
            "e": "12B", "em": "9A",
            "f": "7B", "fm": "4A",
            "gb": "2B", "f#": "2B", "gbm": "11A", "f#m": "11A",
            "g": "9B", "gm": "6A",
            "ab": "4B", "g#": "4B", "abm": "1A", "g#m": "1A",
            "a": "11B", "am": "8A",
            "bb": "6B", "a#": "6B", "bbm": "3A", "a#m": "3A",
            "b": "1B", "bm": "10A",
        }

        return key_to_camelot.get(key_str)
