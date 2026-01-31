"""Local filesystem storage provider."""

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional

import aiofiles

from storage.base import StorageFile, StorageProvider


class LocalStorage(StorageProvider):
    """Local filesystem storage provider."""

    AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aiff', '.aac', '.ogg', '.m4a'}

    def __init__(self, base_path: Optional[str] = None) -> None:
        """Initialize local storage.

        Args:
            base_path: Base directory for storage operations.
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_size: int = 100,
    ) -> AsyncIterator[StorageFile]:
        """List audio files in a folder."""
        folder_path = Path(folder_id) if folder_id else self.base_path

        if not folder_path.exists():
            return

        count = 0
        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.AUDIO_EXTENSIONS:
                yield self._path_to_storage_file(file_path)
                count += 1
                if count >= page_size:
                    break

    async def download(
        self,
        file_id: str,
        destination: str,
    ) -> str:
        """Copy a file to destination."""
        source = Path(file_id)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {file_id}")

        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    async def download_temp(
        self,
        file_id: str,
        temp_dir: Optional[str] = None,
    ) -> str:
        """Copy a file to a temporary location."""
        source = Path(file_id)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {file_id}")

        temp_dir = temp_dir or tempfile.gettempdir()
        fd, temp_path = tempfile.mkstemp(suffix=source.suffix, dir=temp_dir)
        os.close(fd)

        shutil.copy2(source, temp_path)
        return temp_path

    async def upload(
        self,
        local_path: str,
        remote_path: str,
        folder_id: Optional[str] = None,
    ) -> StorageFile:
        """Copy a file to storage location."""
        if folder_id:
            dest_dir = Path(folder_id)
        else:
            dest_dir = self.base_path

        dest_path = dest_dir / remote_path
        os.makedirs(dest_path.parent, exist_ok=True)
        shutil.copy2(local_path, dest_path)

        return self._path_to_storage_file(dest_path)

    async def delete(self, file_id: str) -> bool:
        """Delete a file."""
        try:
            Path(file_id).unlink()
            return True
        except Exception:
            return False

    async def get_file_info(self, file_id: str) -> Optional[StorageFile]:
        """Get file information."""
        path = Path(file_id)
        if not path.exists():
            return None
        return self._path_to_storage_file(path)

    async def search(
        self,
        query: str,
        folder_id: Optional[str] = None,
        file_types: Optional[list[str]] = None,
    ) -> AsyncIterator[StorageFile]:
        """Search for files by name."""
        search_path = Path(folder_id) if folder_id else self.base_path
        query_lower = query.lower()

        for file_path in search_path.rglob('*'):
            if not file_path.is_file():
                continue

            if query_lower not in file_path.name.lower():
                continue

            if file_path.suffix.lower() not in self.AUDIO_EXTENSIONS:
                continue

            yield self._path_to_storage_file(file_path)

    async def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None,
    ) -> StorageFile:
        """Create a folder."""
        if parent_id:
            folder_path = Path(parent_id) / name
        else:
            folder_path = self.base_path / name

        folder_path.mkdir(parents=True, exist_ok=True)

        return StorageFile(
            id=str(folder_path),
            name=name,
            path=str(folder_path),
            size=0,
            mime_type='inode/directory',
            uri=f"file://{folder_path}",
        )

    def get_uri(self, file_id: str) -> str:
        """Get storage URI for a file."""
        return f"file://{file_id}"

    def _path_to_storage_file(self, path: Path) -> StorageFile:
        """Convert Path to StorageFile."""
        stat = path.stat()

        # Calculate MD5 hash
        checksum = None
        if path.is_file() and stat.st_size < 100 * 1024 * 1024:  # < 100MB
            checksum = self._calculate_md5(path)

        # Determine MIME type
        mime_map = {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.aiff': 'audio/aiff',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
        }
        mime_type = mime_map.get(path.suffix.lower(), 'application/octet-stream')

        return StorageFile(
            id=str(path),
            name=path.name,
            path=str(path),
            size=stat.st_size,
            mime_type=mime_type,
            modified_time=str(stat.st_mtime),
            checksum=checksum,
            uri=f"file://{path}",
        )

    def _calculate_md5(self, path: Path) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def scan_directory(
        self,
        directory: str,
        recursive: bool = True,
    ) -> AsyncIterator[StorageFile]:
        """Scan a directory for audio files.

        Args:
            directory: Directory path to scan.
            recursive: Whether to scan subdirectories.

        Yields:
            StorageFile for each audio file found.
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        pattern = '**/*' if recursive else '*'

        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.AUDIO_EXTENSIONS:
                yield self._path_to_storage_file(file_path)
