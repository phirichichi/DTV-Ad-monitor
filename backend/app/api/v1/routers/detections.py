# backend/app/api/v1/routers/detections.py
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.dependencies import require_roles
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.s3_client import S3Client, get_storage_client
from app.models import AdDetectionLog, Advertisement, AuditLog, DetectionEvidence, User

router = APIRouter(prefix="/detections", tags=["Detections"])

class DetectionReviewRequest(BaseModel):
    reason: str | None = None

def _evidence_url(evidence: DetectionEvidence) -> str:
    return f"/api/v1/detections/evidence/{evidence.id}/file"

def _evidence_to_dict(evidence: DetectionEvidence) -> dict:
    return {
        "id": evidence.id,
        "file_path": evidence.file_path,
        "file_url": _evidence_url(evidence),
        "file_type": evidence.file_type,
        "checksum": evidence.checksum,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
    }

@router.get("")
def list_detections(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: Optional[str] = None,
    review_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    query = (
        db.query(AdDetectionLog)
        .options(
            joinedload(AdDetectionLog.channel),
            joinedload(AdDetectionLog.advertisement).joinedload(Advertisement.advertiser),
            joinedload(AdDetectionLog.evidence_items),
        )
        .order_by(AdDetectionLog.detected_at.desc())
    )

    if status:
        query = query.filter(AdDetectionLog.status == status)

    if review_status:
        query = query.filter(AdDetectionLog.review_status == review_status)

    results = query.offset((page - 1) * page_size).limit(page_size).all()

    return [
        {
            "id": item.id,
            "detected_at": item.detected_at.isoformat() if item.detected_at else None,
            "duration_seconds": item.duration_seconds,
            "confidence_score": item.confidence_score,
            "status": item.status,
            "match_source": item.match_source,
            "review_status": item.review_status,
            "notes": item.notes,
            "channel": {
                "id": item.channel.id,
                "name": item.channel.name,
            }
            if item.channel
            else None,
            "advertisement": {
                "id": item.advertisement.id,
                "title": item.advertisement.title,
                "advertiser_name": (
                    item.advertisement.advertiser.name
                    if item.advertisement and item.advertisement.advertiser
                    else None
                ),
            }
            if item.advertisement
            else None,
            "evidence_items": [
                _evidence_to_dict(evidence) for evidence in item.evidence_items
            ],
        }
        for item in results
    ]

@router.get("/evidence/{evidence_id}/file")
def get_evidence_file(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    evidence = db.query(DetectionEvidence).filter(DetectionEvidence.id == evidence_id).first()

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    storage_client = get_storage_client()

    if isinstance(storage_client, S3Client):
        url = storage_client.generate_presigned_url(evidence.file_path)
        return RedirectResponse(url=url)

    path = Path(evidence.file_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence file missing from local storage")

    media_type = "application/octet-stream"

    if evidence.file_type == "screenshot":
        media_type = "image/jpeg"
    elif evidence.file_type == "clip":
        media_type = "video/mp4"

    return FileResponse(path=str(path), media_type=media_type)

@router.post("/{detection_id}/verify")
def verify(
    detection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    detection = db.query(AdDetectionLog).filter(AdDetectionLog.id == detection_id).first()

    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")

    detection.review_status = "verified"

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="VERIFY_DETECTION",
            entity_type="ad_detection_log",
            entity_id=detection.id,
            details=f"Detection {detection.id} verified by {current_user.email}",
        )
    )

    db.commit()

    return {"status": "verified", "detection_id": detection.id}

@router.post("/{detection_id}/reject")
def reject(
    detection_id: int,
    payload: DetectionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    detection = db.query(AdDetectionLog).filter(AdDetectionLog.id == detection_id).first()

    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")

    detection.review_status = "rejected"
    detection.notes = payload.reason or detection.notes

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="REJECT_DETECTION",
            entity_type="ad_detection_log",
            entity_id=detection.id,
            details=(
                f"Detection {detection.id} rejected by {current_user.email}. "
                f"Reason: {payload.reason or 'N/A'}"
            ),
        )
    )

    db.commit()
    return {"status": "rejected", "detection_id": detection.id}