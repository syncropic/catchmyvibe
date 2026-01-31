"""Google Drive storage provider."""

import io
import os
import tempfile
from typing import AsyncIterator, Optional

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from storage.base import StorageFile, StorageProvider


class GoogleDriveStorage(StorageProvider):
    """Google Drive storage provider implementation."""

    AUDIO_MIME_TYPES = [
        'audio/mpeg',
        'audio/mp3',
        'audio/flac',
        'audio/wav',
        'audio/x-wav',
        'audio/aiff',
        'audio/x-aiff',
        'audio/aac',
        'audio/ogg',
        'audio/mp4',
        'audio/x-m4a',
    ]

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        credentials: Optional[Credentials] = None,
    ) -> None:
        """Initialize Google Drive storage.

        Args:
            credentials_file: Path to service account JSON file.
            credentials: OAuth2 credentials object.
        """
        self.credentials = credentials
        self._service = None

        if credentials_file and os.path.exists(credentials_file):
            self.credentials = ServiceAccountCredentials.from_service_account_file(
                credentials_file,
                scopes=['https://www.googleapis.com/auth/drive']
            )

    @property
    def service(self):
        """Get or create Drive API service."""
        if self._service is None:
            if self.credentials is None:
                raise ValueError("No credentials provided for Google Drive")
            self._service = build('drive', 'v3', credentials=self.credentials)
        return self._service

    async def list_files(
        self,
        folder_id: Optional[str] = None,
        page_size: int = 100,
    ) -> AsyncIterator[StorageFile]:
        """List files in a folder."""
        query_parts = ["trashed = false"]

        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")

        # Filter to audio files
        mime_conditions = " or ".join(
            f"mimeType = '{mime}'" for mime in self.AUDIO_MIME_TYPES
        )
        query_parts.append(f"({mime_conditions})")

        query = " and ".join(query_parts)
        page_token = None

        while True:
            response = self.service.files().list(
                q=query,
                pageSize=page_size,
                pageToken=page_token,
                fields="nextPageToken, files(id, name, size, mimeType, modifiedTime, md5Checksum)",
            ).execute()

            for file_data in response.get('files', []):
                yield self._to_storage_file(file_data)

            page_token = response.get('nextPageToken')
            if not page_token:
                break

    async def download(
        self,
        file_id: str,
        destination: str,
    ) -> str:
        """Download a file to local path."""
        request = self.service.files().get_media(fileId=file_id)

        os.makedirs(os.path.dirname(destination), exist_ok=True)

        with open(destination, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return destination

    async def download_temp(
        self,
        file_id: str,
        temp_dir: Optional[str] = None,
    ) -> str:
        """Download a file to a temporary location."""
        # Get file info to get original name
        file_info = await self.get_file_info(file_id)
        if not file_info:
            raise FileNotFoundError(f"File not found: {file_id}")

        # Create temp file with appropriate extension
        ext = os.path.splitext(file_info.name)[1] or '.mp3'
        temp_dir = temp_dir or tempfile.gettempdir()

        fd, temp_path = tempfile.mkstemp(suffix=ext, dir=temp_dir)
        os.close(fd)

        return await self.download(file_id, temp_path)

    async def upload(
        self,
        local_path: str,
        remote_path: str,
        folder_id: Optional[str] = None,
    ) -> StorageFile:
        """Upload a file to storage."""
        file_metadata = {
            'name': remote_path,
        }
        if folder_id:
            file_metadata['parents'] = [folder_id]

        # Determine MIME type
        ext = os.path.splitext(local_path)[1].lower()
        mime_map = {
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.wav': 'audio/wav',
            '.aiff': 'audio/aiff',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
        }
        mime_type = mime_map.get(ext, 'application/octet-stream')

        media = MediaFileUpload(
            local_path,
            mimetype=mime_type,
            resumable=True,
        )

        response = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, size, mimeType, modifiedTime, md5Checksum',
        ).execute()

        return self._to_storage_file(response)

    async def delete(self, file_id: str) -> bool:
        """Delete a file from storage."""
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception:
            return False

    async def get_file_info(self, file_id: str) -> Optional[StorageFile]:
        """Get file information."""
        try:
            response = self.service.files().get(
                fileId=file_id,
                fields='id, name, size, mimeType, modifiedTime, md5Checksum',
            ).execute()
            return self._to_storage_file(response)
        except Exception:
            return None

    async def search(
        self,
        query: str,
        folder_id: Optional[str] = None,
        file_types: Optional[list[str]] = None,
    ) -> AsyncIterator[StorageFile]:
        """Search for files."""
        query_parts = [
            "trashed = false",
            f"name contains '{query}'",
        ]

        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")

        if file_types:
            mime_conditions = " or ".join(
                f"mimeType = '{mime}'" for mime in file_types
            )
            query_parts.append(f"({mime_conditions})")

        search_query = " and ".join(query_parts)

        response = self.service.files().list(
            q=search_query,
            pageSize=50,
            fields="files(id, name, size, mimeType, modifiedTime, md5Checksum)",
        ).execute()

        for file_data in response.get('files', []):
            yield self._to_storage_file(file_data)

    async def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None,
    ) -> StorageFile:
        """Create a folder."""
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]

        response = self.service.files().create(
            body=file_metadata,
            fields='id, name, mimeType, modifiedTime',
        ).execute()

        return self._to_storage_file(response)

    def get_uri(self, file_id: str) -> str:
        """Get storage URI for a file."""
        return f"gdrive://{file_id}"

    def _to_storage_file(self, data: dict) -> StorageFile:
        """Convert API response to StorageFile."""
        return StorageFile(
            id=data.get('id', ''),
            name=data.get('name', ''),
            path=data.get('name', ''),
            size=int(data.get('size', 0)),
            mime_type=data.get('mimeType'),
            modified_time=data.get('modifiedTime'),
            checksum=data.get('md5Checksum'),
            uri=f"gdrive://{data.get('id', '')}",
        )

    @classmethod
    def from_oauth_token(cls, token: dict) -> "GoogleDriveStorage":
        """Create storage from OAuth token dict.

        Args:
            token: OAuth token dict with access_token, refresh_token, etc.

        Returns:
            GoogleDriveStorage instance.
        """
        credentials = Credentials(
            token=token.get('access_token'),
            refresh_token=token.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=token.get('client_id'),
            client_secret=token.get('client_secret'),
        )
        return cls(credentials=credentials)
