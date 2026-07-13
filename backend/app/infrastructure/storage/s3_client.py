import logging
import shutil
from pathlib import Path
from typing import BinaryIO, Optional

from app.core.config import get_settings
logger = logging.getLogger("dtv.storage")

class LocalStorageClient:
    def __init__(self, base_dir: str = "storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, source_path: str, target_key: str) -> str:
        destination = self.base_dir / target_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        logger.info("local_storage_saved source=%s dest=%s", source_path, destination)
        return str(destination)

    def save_bytes(self, data: bytes, target_key: str) -> str:
        destination = self.base_dir / target_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        logger.info("local_storage_saved_bytes dest=%s", destination)
        return str(destination)

    def save_stream(self, file_obj: BinaryIO, target_key: str) -> str:
        destination = self.base_dir / target_key
        destination.parent.mkdir(parents=True, exist_ok=True)

        with open(destination, "wb") as output_file:
            shutil.copyfileobj(file_obj, output_file)

        logger.info("local_storage_saved_stream dest=%s", destination)
        return str(destination)

    def exists(self, target_key: str) -> bool:
        return (self.base_dir / target_key).exists()

    def get_path(self, target_key: str) -> str:
        return str(self.base_dir / target_key)

    def delete_file(self, stored_path_or_key: str) -> None:
        path = Path(stored_path_or_key)

        if not path.is_absolute() and not str(path).startswith(str(self.base_dir)):
            path = self.base_dir / stored_path_or_key

        try:
            path.unlink(missing_ok=True)
            logger.info("local_storage_deleted path=%s", path)
        except Exception:
            logger.exception("local_storage_delete_failed path=%s", path)

class S3Client:
    def __init__(self):
        settings = get_settings()

        if not settings.s3_bucket_name:
            raise RuntimeError("S3 bucket name is missing")
        if not settings.s3_access_key or not settings.s3_secret_key:
            raise RuntimeError("S3 credentials are missing")
        if not settings.s3_endpoint:
            raise RuntimeError("S3 endpoint is missing")
        import boto3
        from botocore.client import Config
        self.bucket = settings.s3_bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4"),
            region_name=settings.s3_region,
        )

    def save_file(self, source_path: str, target_key: str) -> str:
        self.client.upload_file(source_path, self.bucket, target_key)
        logger.info("s3_storage_saved source=%s key=%s", source_path, target_key)
        return target_key

    def save_bytes(self, data: bytes, target_key: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=target_key, Body=data)
        logger.info("s3_storage_saved_bytes key=%s", target_key)
        return target_key

    def save_stream(self, file_obj: BinaryIO, target_key: str) -> str:
        self.client.upload_fileobj(file_obj, self.bucket, target_key)
        logger.info("s3_storage_saved_stream key=%s", target_key)
        return target_key

    def get_path(self, target_key: str) -> str:
        return target_key

    def delete_file(self, target_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=target_key)
            logger.info("s3_storage_deleted key=%s", target_key)
        except Exception:
            logger.exception("s3_storage_delete_failed key=%s", target_key)

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

def get_storage_client(mode: Optional[str] = None, base_dir: Optional[str] = None):
    settings = get_settings()
    resolved_mode = mode or settings.storage_mode
    resolved_base_dir = base_dir or settings.local_storage_base_dir
    if resolved_mode == "s3":
        return S3Client()
    return LocalStorageClient(base_dir=resolved_base_dir)