import hashlib
import logging
from pathlib import Path
import cv2

from app.infrastructure.storage.s3_client import get_storage_client
from app.models import DetectionEvidence
logger = logging.getLogger("dtv.screenshot_service")

def _checksum(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save_detection_screenshot(detection_id: int, frame, db):
    local_path = f"/tmp/detection_{detection_id}.jpg"
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)

    success = cv2.imwrite(local_path, frame)
    if not success:
        raise RuntimeError("Failed to write detection screenshot")

    storage = get_storage_client()
    key = f"detections/screenshots/{detection_id}.jpg"
    stored_path = storage.save_file(local_path, key)
    evidence = DetectionEvidence(
        detection_id=detection_id,
        file_path=stored_path,
        file_type="screenshot",
        checksum=_checksum(local_path),
    )
    db.add(evidence)

    try:
        Path(local_path).unlink(missing_ok=True)
    except Exception:
        logger.exception("temp_screenshot_cleanup_failed path=%s", local_path)
    return stored_path