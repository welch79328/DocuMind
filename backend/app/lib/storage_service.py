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

    async def upload_file(
        self,
        filename: str,
        file_content: bytes,
        path_prefix: str = "uploads",
        acl: str = "public-read"
    ) -> str:
        """上傳檔案並回傳 URL/路徑"""
        if self.storage_type == 'local':
            return await self._upload_local(filename, file_content, path_prefix)
        else:
            return await self._upload_s3(filename, file_content, path_prefix, acl)

    async def download_file(self, file_url: str) -> bytes:
        """下載檔案"""
        if self.storage_type == 'local':
            return await self._download_local(file_url)
        else:
            return await self._download_s3(file_url)

    async def _upload_local(self, filename: str, file_content: bytes, path_prefix: str) -> str:
        """上傳至本地檔案系統"""
        file_extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())

        # 移除 path_prefix 開頭的 uploads/（避免與 upload_dir 重複）
        clean_prefix = path_prefix
        if clean_prefix.startswith("uploads/"):
            clean_prefix = clean_prefix[len("uploads/"):]

        # 建立子目錄
        target_dir = self.upload_dir / clean_prefix
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / unique_filename
        with open(file_path, 'wb') as f:
            f.write(file_content)

        return str(file_path)

    async def _download_local(self, file_path: str) -> bytes:
        """從本地檔案系統下載"""
        with open(file_path, 'rb') as f:
            return f.read()

    async def _upload_s3(self, filename: str, file_content: bytes, path_prefix: str, acl: str) -> str:
        """上傳至 S3/R2"""
        from app.lib.s3_service import upload_file_to_s3
        return await upload_file_to_s3(filename, file_content, path_prefix=path_prefix, acl=acl)

    async def _download_s3(self, file_url: str) -> bytes:
        """從 S3/R2 下載"""
        from app.lib.s3_service import download_file_from_s3
        return await download_file_from_s3(file_url)


# Global storage service instance
storage_service = StorageService()
