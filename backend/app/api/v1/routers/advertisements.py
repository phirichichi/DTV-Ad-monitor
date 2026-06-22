#backend/app/api/v1/routers/advertisements.py
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
from enum import Enum
from pathlib import Path
from uuid import uuid4

import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.dependencies import require_roles
from app.infrastructure.ai.audio_fingerprint import generate_audio_fingerprint
from app.infrastructure.ai.frame_hashing import generate_frame_hash
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.s3_client import get_storage_client
from app.models import Advertisement, Advertiser, AuditLog, User

logger = logging.getLogger("dtv.advertisements")

router = APIRouter(prefix="/advertisements", tags=["Advertisements"])
settings = get_settings()

UPLOAD_DIR = Path(settings.local_upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
    "application/octet-stream",
}

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
}

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


class AdvertisementContentType(str, Enum):
    commercial = "commercial"
    promo = "promo"
    sponsorship = "sponsorship"
    filler = "filler"


class AdvertisementStatusUpdateRequest(BaseModel):
    is_active: bool


class AdvertisementResponse(BaseModel):
    id: int
    advertiser_id: int
    advertiser_name: str
    title: str
    duration_seconds: int
    content_type: str
    reference_audio_signature: str | None = None
    reference_frame_hash: str | None = None
    uploaded_file_name: str | None = None
    uploaded_file_path: str | None = None
    uploaded_mime_type: str | None = None
    uploaded_file_size_bytes: int | None = None
    is_active: bool

    class Config:
        from_attributes = True


def _to_response(ad: Advertisement) -> AdvertisementResponse:
    return AdvertisementResponse(
        id=ad.id,
        advertiser_id=ad.advertiser_id,
        advertiser_name=ad.advertiser.name if ad.advertiser else "Unknown",
        title=ad.title,
        duration_seconds=ad.duration_seconds,
        content_type=ad.content_type,
        reference_audio_signature=ad.reference_audio_signature,
        reference_frame_hash=ad.reference_frame_hash,
        uploaded_file_name=ad.uploaded_file_name,
        uploaded_file_path=ad.uploaded_file_path,
        uploaded_mime_type=ad.uploaded_mime_type,
        uploaded_file_size_bytes=ad.uploaded_file_size_bytes,
        is_active=ad.is_active,
    )


def _validate_upload_file(video_file: UploadFile, extension: str) -> None:
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video extension: {extension}",
        )

    if video_file.content_type and video_file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video file type: {video_file.content_type}",
        )


def _extract_audio_wav(video_path: str, output_wav_path: str) -> str:
    cmd = [
        settings.ffmpeg_binary_path,
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        output_wav_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to extract audio from uploaded video: {result.stderr}")

    return output_wav_path


def _read_video_duration_seconds(video_path: str) -> int:
    capture = cv2.VideoCapture(video_path)

    try:
        if capture.isOpened():
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)

            if fps > 0 and frame_count > 0:
                return max(1, int(math.ceil(frame_count / fps)))
    finally:
        capture.release()

    ffprobe_path = settings.ffmpeg_binary_path.replace("ffmpeg", "ffprobe")

    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        return max(1, int(math.ceil(float(result.stdout.strip()))))

    raise RuntimeError("Could not determine video duration")


def _extract_reference_hashes(video_path: str) -> str:
    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():
        raise RuntimeError(f"Failed to open uploaded video for frame extraction: {video_path}")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if frame_count <= 0:
            success, frame = capture.read()
            if not success or frame is None:
                raise RuntimeError("No readable frame found in uploaded video")

            payload = {
                "version": "ad-reference-frame-set-v1",
                "keyframes": [json.loads(generate_frame_hash(frame))],
            }
            return json.dumps(payload, separators=(",", ":"))

        candidate_positions = sorted(
            {
                max(int(frame_count * 0.15), 0),
                max(int(frame_count * 0.50), 0),
                max(int(frame_count * 0.85), 0),
            }
        )

        keyframes = []

        for pos in candidate_positions:
            capture.set(cv2.CAP_PROP_POS_FRAMES, pos)
            success, frame = capture.read()

            if success and frame is not None:
                keyframes.append(json.loads(generate_frame_hash(frame)))

        if not keyframes:
            raise RuntimeError("Failed to extract keyframes from uploaded video")

        payload = {
            "version": "ad-reference-frame-set-v1",
            "keyframes": keyframes,
        }

        return json.dumps(payload, separators=(",", ":"))

    finally:
        capture.release()


def _extract_reference_audio_signature(video_path: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        _extract_audio_wav(video_path, wav_path)
        return generate_audio_fingerprint(wav_path)
    finally:
        try:
            Path(wav_path).unlink(missing_ok=True)
        except Exception:
            logger.exception("temp_audio_cleanup_failed path=%s", wav_path)


@router.post(
    "/upload",
    response_model=AdvertisementResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_advertisement_video(
    advertiser_id: int = Form(...),
    title: str = Form(...),
    content_type: AdvertisementContentType = Form(AdvertisementContentType.commercial),
    is_active: bool = Form(True),
    video_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    title = title.strip()

    if not title:
        raise HTTPException(status_code=400, detail="Advertisement title is required")

    advertiser = (
        db.query(Advertiser)
        .filter(Advertiser.id == advertiser_id, Advertiser.is_archived.is_(False))
        .first()
    )

    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")

    original_name = video_file.filename or "uploaded_video.mp4"
    extension = Path(original_name).suffix.lower() or ".mp4"

    _validate_upload_file(video_file, extension)

    safe_name = f"{uuid4().hex}{extension}"
    save_path = UPLOAD_DIR / safe_name
    stored_path: str | None = None

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)

        file_size = os.path.getsize(save_path)

        if file_size <= 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Uploaded file exceeds size limit")

        duration_seconds = _read_video_duration_seconds(str(save_path))
        reference_frame_hash = _extract_reference_hashes(str(save_path))
        reference_audio_signature = _extract_reference_audio_signature(str(save_path))

        storage_client = get_storage_client()
        storage_key = f"ads/reference_videos/{safe_name}"
        stored_path = storage_client.save_file(str(save_path), storage_key)

        ad = Advertisement(
            advertiser_id=advertiser_id,
            title=title,
            duration_seconds=duration_seconds,
            content_type=content_type.value,
            reference_audio_signature=reference_audio_signature,
            reference_frame_hash=reference_frame_hash,
            uploaded_file_name=original_name,
            uploaded_file_path=stored_path,
            uploaded_mime_type=video_file.content_type,
            uploaded_file_size_bytes=file_size,
            is_active=is_active,
        )

        db.add(ad)
        db.flush()

        db.add(
            AuditLog(
                user_id=current_user.id,
                action="UPLOAD_ADVERTISEMENT_VIDEO",
                entity_type="advertisement",
                entity_id=ad.id,
                details=(
                    f"Uploaded reference video and generated signatures for "
                    f"advertisement {ad.title}"
                ),
            )
        )

        db.commit()
        db.refresh(ad)

        return _to_response(ad)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        if stored_path:
            try:
                get_storage_client().delete_file(stored_path)
            except Exception:
                logger.exception("stored_reference_cleanup_failed path=%s", stored_path)

        logger.exception("advertisement_upload_failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process uploaded video: {str(exc)}",
        ) from exc

    finally:
        try:
            save_path.unlink(missing_ok=True)
        except Exception:
            logger.exception("temp_video_cleanup_failed path=%s", save_path)


@router.get("", response_model=list[AdvertisementResponse])
def list_advertisements(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    ads = (
        db.query(Advertisement)
        .options(joinedload(Advertisement.advertiser))
        .order_by(Advertisement.created_at.desc())
        .all()
    )

    return [_to_response(ad) for ad in ads]


@router.patch("/{advertisement_id}/status", response_model=AdvertisementResponse)
def update_advertisement_status(
    advertisement_id: int,
    payload: AdvertisementStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    ad = (
        db.query(Advertisement)
        .options(joinedload(Advertisement.advertiser))
        .filter(Advertisement.id == advertisement_id)
        .first()
    )

    if not ad:
        raise HTTPException(status_code=404, detail="Advertisement not found")

    ad.is_active = payload.is_active

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="UPDATE_ADVERTISEMENT_STATUS",
            entity_type="advertisement",
            entity_id=ad.id,
            details=f"Set advertisement {ad.title} active={payload.is_active}",
        )
    )

    db.commit()
    db.refresh(ad)

    return _to_response(ad)