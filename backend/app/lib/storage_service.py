"""
Storage Service - Unified interface for file storage (Local or S3/R2)
"""

import os
import uuid
from pathlib import Path
from app.config import settings


class StorageService:
    """Unified storage service supporting local and S3/R2"""

    def __init__(self):
        self.storage_type = getattr(settings, 'STORAGE_TYPE', 'local')
        if self.storage_type == 'local':
            self.upload_dir = Path(getattr(settings, 'LOCAL_STORAGE_PATH', '/app/uploads'))
            self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_file(self, filename: str, file_content: bytes) -> str:
        """Upload file and return URL/path"""
        if self.storage_type == 'local':
            return await self._upload_local(filename, file_content)
        else:
            return await self._upload_s3(filename, file_content)

    async def download_file(self, file_url: str) -> bytes:
        """Download file from storage"""
        if self.storage_type == 'local':
            return await self._download_local(file_url)
        else:
            return await self._download_s3(file_url)

    async def _upload_local(self, filename: str, file_content: bytes) -> str:
        """Upload to local filesystem"""
        # Generate unique filename
        file_extension = filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # Save file
        file_path = self.upload_dir / unique_filename
        with open(file_path, 'wb') as f:
            f.write(file_content)

        # Return local path (used as URL)
        return str(file_path)

    async def _download_local(self, file_path: str) -> bytes:
        """Download from local filesystem"""
        with open(file_path, 'rb') as f:
            return f.read()

    async def _upload_s3(self, filename: str, file_content: bytes) -> str:
        """Upload to S3/R2"""
        from app.lib.s3_service import upload_file_to_s3
        return await upload_file_to_s3(filename, file_content)

    async def _download_s3(self, file_url: str) -> bytes:
        """Download from S3/R2"""
        from app.lib.s3_service import download_file_from_s3
        return await download_file_from_s3(file_url)


# Global storage service instance
storage_service = StorageService()
