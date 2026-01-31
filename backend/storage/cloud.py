"""Unified cloud storage interface."""

import os
from typing import Optional

from storage.base import StorageFile, StorageProvider
from storage.google_drive import GoogleDriveStorage
from storage.local import LocalStorage


class CloudStorage:
    """Unified cloud storage interface.

    Automatically routes operations to the appropriate storage provider
    based on URI scheme.
    """

    def __init__(self) -> None:
        """Initialize cloud storage with providers."""
        self._providers: dict[str, StorageProvider] = {}
        self._default_provider: Optional[StorageProvider] = None

    def register_provider(
        self,
        scheme: str,
        provider: StorageProvider,
        default: bool = False,
    ) -> None:
        """Register a storage provider.

        Args:
            scheme: URI scheme (e.g., "gdrive", "s3", "file").
            provider: Storage provider instance.
            default: Whether this is the default provider.
        """
        self._providers[scheme] = provider
        if default:
            self._default_provider = provider

    def _get_provider(self, uri: str) -> tuple[StorageProvider, str]:
        """Get provider and file ID from URI.

        Args:
            uri: Storage URI (e.g., "gdrive://file_id", "file:///path").

        Returns:
            Tuple of (provider, file_id).
        """
        if '://' in uri:
            scheme, rest = uri.split('://', 1)
            scheme = scheme.lower()

            if scheme in self._providers:
                return self._providers[scheme], rest
            elif scheme == 'file':
                # Local file path
                if 'file' not in self._providers:
                    self._providers['file'] = LocalStorage()
                return self._providers['file'], rest
            else:
                raise ValueError(f"Unknown storage scheme: {scheme}")
        else:
            # Assume local file
            if 'file' not in self._providers:
                self._providers['file'] = LocalStorage()
            return self._providers['file'], uri

    async def download_temp(
        self,
        uri: str,
        temp_dir: Optional[str] = None,
    ) -> str:
        """Download a file to a temporary location.

        Args:
            uri: Storage URI.
            temp_dir: Directory for temp file.

        Returns:
            Path to temporary file.
        """
        provider, file_id = self._get_provider(uri)
        return await provider.download_temp(file_id, temp_dir)

    async def download(
        self,
        uri: str,
        destination: str,
    ) -> str:
        """Download a file to a specific location.

        Args:
            uri: Storage URI.
            destination: Local destination path.

        Returns:
            Path to downloaded file.
        """
        provider, file_id = self._get_provider(uri)
        return await provider.download(file_id, destination)

    async def upload(
        self,
        local_path: str,
        uri: str,
    ) -> StorageFile:
        """Upload a file to cloud storage.

        Args:
            local_path: Path to local file.
            uri: Destination URI.

        Returns:
            StorageFile for uploaded file.
        """
        provider, remote_path = self._get_provider(uri)
        return await provider.upload(local_path, remote_path)

    async def get_file_info(self, uri: str) -> Optional[StorageFile]:
        """Get file information.

        Args:
            uri: Storage URI.

        Returns:
            StorageFile or None if not found.
        """
        provider, file_id = self._get_provider(uri)
        return await provider.get_file_info(file_id)

    async def delete(self, uri: str) -> bool:
        """Delete a file.

        Args:
            uri: Storage URI.

        Returns:
            True if deleted successfully.
        """
        provider, file_id = self._get_provider(uri)
        return await provider.delete(file_id)

    @classmethod
    def from_config(cls) -> "CloudStorage":
        """Create CloudStorage from environment configuration.

        Returns:
            Configured CloudStorage instance.
        """
        storage = cls()

        # Register local storage
        storage.register_provider('file', LocalStorage())

        # Register Google Drive if configured
        gdrive_creds = os.environ.get('GOOGLE_DRIVE_CREDENTIALS_FILE')
        if gdrive_creds and os.path.exists(gdrive_creds):
            storage.register_provider(
                'gdrive',
                GoogleDriveStorage(credentials_file=gdrive_creds),
                default=True,
            )

        return storage
