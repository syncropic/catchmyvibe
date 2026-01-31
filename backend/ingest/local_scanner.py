"""Local file system scanner for audio files."""

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from mutagen import File as MutagenFile


@dataclass
class ScannedTrack:
    """Represents a scanned audio file."""

    file_path: str
    file_hash: str
    file_size: int

    # Metadata from tags
    title: str
    artists: list[str] = field(default_factory=list)
    album: Optional[str] = None
    genre: Optional[str] = None
    release_year: Optional[int] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    duration_ms: Optional[int] = None
    comment: Optional[str] = None


class LocalScanner:
    """Scanner for local audio files."""

    AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aiff', '.aac', '.ogg', '.m4a'}

    def __init__(self) -> None:
        """Initialize the scanner."""
        pass

    def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> Iterator[ScannedTrack]:
        """Scan a directory for audio files.

        Args:
            directory: Directory path to scan.
            recursive: Whether to scan subdirectories.

        Yields:
            ScannedTrack for each audio file found.
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        pattern = '**/*' if recursive else '*'

        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.AUDIO_EXTENSIONS:
                try:
                    track = self._scan_file(file_path)
                    if track:
                        yield track
                except Exception as e:
                    print(f"Error scanning {file_path}: {e}")

    def scan_file(self, file_path: str) -> Optional[ScannedTrack]:
        """Scan a single audio file.

        Args:
            file_path: Path to audio file.

        Returns:
            ScannedTrack or None if file can't be read.
        """
        path = Path(file_path)
        if not path.exists():
            return None

        if path.suffix.lower() not in self.AUDIO_EXTENSIONS:
            return None

        return self._scan_file(path)

    def _scan_file(self, path: Path) -> Optional[ScannedTrack]:
        """Internal method to scan a file.

        Args:
            path: Path object for audio file.

        Returns:
            ScannedTrack or None.
        """
        try:
            audio = MutagenFile(str(path))
            if audio is None:
                return None

            # Calculate file hash
            file_hash = self._calculate_hash(path)
            file_size = path.stat().st_size

            # Extract metadata
            title = self._get_tag(audio, ['title', 'TIT2', '\xa9nam']) or path.stem

            artist = self._get_tag(audio, ['artist', 'TPE1', '\xa9ART']) or ''
            artists = [a.strip() for a in artist.split(',') if a.strip()]

            album = self._get_tag(audio, ['album', 'TALB', '\xa9alb'])
            genre = self._get_tag(audio, ['genre', 'TCON', '\xa9gen'])
            comment = self._get_tag(audio, ['comment', 'COMM', '\xa9cmt'])

            # Get BPM
            bpm_str = self._get_tag(audio, ['bpm', 'TBPM'])
            bpm = None
            if bpm_str:
                try:
                    bpm = float(bpm_str)
                except ValueError:
                    pass

            # Get key
            key = self._get_tag(audio, ['initialkey', 'TKEY', 'key'])

            # Get year
            year_str = self._get_tag(audio, ['date', 'TDRC', '\xa9day', 'year'])
            year = None
            if year_str:
                try:
                    year = int(str(year_str)[:4])
                except ValueError:
                    pass

            # Get duration
            duration_ms = None
            if hasattr(audio.info, 'length'):
                duration_ms = int(audio.info.length * 1000)

            return ScannedTrack(
                file_path=str(path),
                file_hash=file_hash,
                file_size=file_size,
                title=title,
                artists=artists,
                album=album,
                genre=genre,
                release_year=year,
                bpm=bpm,
                key=key,
                duration_ms=duration_ms,
                comment=comment,
            )

        except Exception as e:
            print(f"Error reading {path}: {e}")
            return None

    def _get_tag(self, audio: MutagenFile, tag_names: list[str]) -> Optional[str]:
        """Get a tag value from various possible tag names.

        Args:
            audio: Mutagen file object.
            tag_names: List of possible tag names.

        Returns:
            Tag value or None.
        """
        if not hasattr(audio, 'tags') or audio.tags is None:
            # Try direct attribute access for some formats
            for name in tag_names:
                if hasattr(audio, name):
                    val = getattr(audio, name)
                    if val:
                        return str(val[0]) if isinstance(val, list) else str(val)
            return None

        for name in tag_names:
            value = audio.tags.get(name)
            if value:
                if isinstance(value, list):
                    return str(value[0])
                return str(value)

        # Try with different tag class patterns
        for key in audio.tags.keys():
            for name in tag_names:
                if name.lower() in key.lower():
                    value = audio.tags[key]
                    if isinstance(value, list):
                        return str(value[0])
                    return str(value)

        return None

    def _calculate_hash(self, path: Path, chunk_size: int = 8192) -> str:
        """Calculate SHA-256 hash of a file.

        For large files, only hashes the first 1MB for speed.

        Args:
            path: Path to file.
            chunk_size: Chunk size for reading.

        Returns:
            Hex digest of hash.
        """
        hash_sha256 = hashlib.sha256()
        bytes_read = 0
        max_bytes = 1024 * 1024  # 1MB

        with open(path, 'rb') as f:
            while bytes_read < max_bytes:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hash_sha256.update(chunk)
                bytes_read += len(chunk)

            # Also include file size in hash for uniqueness
            hash_sha256.update(str(path.stat().st_size).encode())

        return hash_sha256.hexdigest()

    def find_duplicates(
        self,
        directory: str,
        recursive: bool = True,
    ) -> dict[str, list[str]]:
        """Find duplicate audio files based on hash.

        Args:
            directory: Directory to scan.
            recursive: Whether to scan subdirectories.

        Returns:
            Dict mapping hash to list of file paths with that hash.
        """
        hash_to_paths: dict[str, list[str]] = {}

        for track in self.scan_directory(directory, recursive):
            if track.file_hash not in hash_to_paths:
                hash_to_paths[track.file_hash] = []
            hash_to_paths[track.file_hash].append(track.file_path)

        # Filter to only duplicates
        return {h: paths for h, paths in hash_to_paths.items() if len(paths) > 1}
