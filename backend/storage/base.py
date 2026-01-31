"""Base storage provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class StorageFile:
    """Represents a file in storage."""

    id: str
    name: str
    path: str
    size: int
    mime_type: Optional[str] = None
    modified_time: Optional[str] = None
    checksum: Optional[str] = None
    uri: Optional[str] = None


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_size: int = 100,
    ) -> AsyncIterator[StorageFile]:
        """List files in a folder.

        Args:
            folder_id: ID of folder to list (root if None).
            page_size: Number of files per page.

        Yields:
            StorageFile objects.
        """
        pass

    @abstractmethod
    async def download(
        self,
        file_id: str,
        destination: str,
    ) -> str:
        """Download a file to local path.

        Args:
            file_id: ID of file to download.
            destination: Local path to save file.

        Returns:
            Path to downloaded file.
        """
        pass

    @abstractmethod
    async def download_temp(
        self,
        file_id: str,
        temp_dir: Optional[str] = None,
    ) -> str:
        """Download a file to a temporary location.

        Args:
            file_id: ID of file to download.
            temp_dir: Directory for temp file.

        Returns:
            Path to temporary file.
        """
        pass

    @abstractmethod
    async def upload(
        self,
        local_path: str,
        remote_path: str,
        folder_id: Optional[str] = None,
    ) -> StorageFile:
        """Upload a file to storage.

        Args:
            local_path: Path to local file.
            remote_path: Remote file name/path.
            folder_id: ID of destination folder.

        Returns:
            StorageFile object for uploaded file.
        """
        pass

    @abstractmethod
    async def delete(self, file_id: str) -> bool:
        """Delete a file from storage.

        Args:
            file_id: ID of file to delete.

        Returns:
            True if deleted successfully.
        """
        pass

    @abstractmethod
    async def get_file_info(self, file_id: str) -> Optional[StorageFile]:
        """Get file information.

        Args:
            file_id: ID of file.

        Returns:
            StorageFile object or None if not found.
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        folder_id: Optional[str] = None,
        file_types: Optional[list[str]] = None,
    ) -> AsyncIterator[StorageFile]:
        """Search for files.

        Args:
            query: Search query.
            folder_id: Limit search to folder.
            file_types: Filter by MIME types.

        Yields:
            Matching StorageFile objects.
        """
        pass

    @abstractmethod
    async def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None,
    ) -> StorageFile:
        """Create a folder.

        Args:
            name: Folder name.
            parent_id: Parent folder ID.

        Returns:
            StorageFile object for created folder.
        """
        pass

    @abstractmethod
    def get_uri(self, file_id: str) -> str:
        """Get storage URI for a file.

        Args:
            file_id: File ID.

        Returns:
            URI string (e.g., "gdrive://file_id").
        """
        pass
