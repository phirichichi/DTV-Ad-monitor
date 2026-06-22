from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
import csv


from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload


from app.dependencies import require_roles
from app.infrastructure.db.session import get_db
from app.models import (
    AdDetectionLog,
    Advertisement,
    Advertiser,
    AuditLog,
    Channel,
    DetectionEvidence,
    User,
)


router = APIRouter(prefix="/reports", tags=["Reports"])


def _parse_range(
    start_date: str | None,
    end_date: str | None,
    last_24_hours: bool,
) -> tuple[datetime | None, datetime | None]:
    if last_24_hours:
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(hours=24)
        return start_dt, end_dt


    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00") if start_date else None
    end_dt = datetime.fromisoformat(f"{end_date}T23:59:59") if end_date else None


    return start_dt, end_dt


def _evidence_url(evidence: DetectionEvidence | None) -> str | None:
    if not evidence:
        return None
    return f"/api/v1/detections/evidence/{evidence.id}/file"


def _split_date_time(value: datetime | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    return value.date().isoformat(), value.time().replace(microsecond=0).isoformat()


def _build_report_rows(
    db: Session,
    start_dt: datetime | None,
    end_dt: datetime | None,
    channel_id: int | None = None,
    advertiser_id: int | None = None,
    advertisement_id: int | None = None,
    status: str | None = None,
    review_status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    query = (
        db.query(AdDetectionLog)
        .outerjoin(AdDetectionLog.channel)
        .outerjoin(AdDetectionLog.advertisement)
        .outerjoin(Advertisement.advertiser)
        .options(
            joinedload(AdDetectionLog.channel),
            joinedload(AdDetectionLog.advertisement).joinedload(Advertisement.advertiser),
            joinedload(AdDetectionLog.evidence_items),
        )
        .order_by(AdDetectionLog.detected_at.desc())
    )


    if start_dt:
        query = query.filter(AdDetectionLog.detected_at >= start_dt)
    if end_dt:
        query = query.filter(AdDetectionLog.detected_at <= end_dt)
    if channel_id:
        query = query.filter(AdDetectionLog.channel_id == channel_id)
    if advertisement_id:
        query = query.filter(AdDetectionLog.advertisement_id == advertisement_id)
    if advertiser_id:
        query = query.filter(Advertisement.advertiser_id == advertiser_id)
    if status:
        query = query.filter(AdDetectionLog.status == status)
    if review_status:
        query = query.filter(AdDetectionLog.review_status == review_status)


    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Advertiser.name.ilike(pattern),
                Advertisement.title.ilike(pattern),
                Channel.name.ilike(pattern),
                AdDetectionLog.status.ilike(pattern),
                AdDetectionLog.review_status.ilike(pattern),
            )
        )


    output: list[dict] = []


    for row in query.all():
        screenshot = None


        for evidence in row.evidence_items:
            if evidence.file_type == "screenshot":
                screenshot = evidence
                break


        # ✅ UPDATED: Use started_at and ended_at
        date_played, start_time = _split_date_time(row.started_at)


        _, end_time = _split_date_time(row.ended_at)


        # ✅ UPDATED: New output structure
        output.append(
            {
                "detection_id": row.id,


                "date": date_played,


                "advertiser": (
                    row.advertisement.advertiser.name
                    if row.advertisement and row.advertisement.advertiser
                    else "Unknown"
                ),


                "ad_name": (
                    row.advertisement.title
                    if row.advertisement
                    else "Unknown"
                ),


                "start_time": start_time,


                "end_time": end_time,


                "duration": row.duration_seconds,
            }
        )
    return output


@router.get("/")
def list_reports(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    last_24_hours: bool = Query(False),
    channel_id: int | None = Query(None),
    advertiser_id: int | None = Query(None),
    advertisement_id: int | None = Query(None),
    status: str | None = Query(None),
    review_status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    start_dt, end_dt = _parse_range(start_date, end_date, last_24_hours)


    return _build_report_rows(
        db=db,
        start_dt=start_dt,
        end_dt=end_dt,
        channel_id=channel_id,
        advertiser_id=advertiser_id,
        advertisement_id=advertisement_id,
        status=status,
        review_status=review_status,
        search=search,
    )


def _export_rows(
    db: Session,
    start_date: str | None,
    end_date: str | None,
    last_24_hours: bool,
    channel_id: int | None,
    advertiser_id: int | None,
    advertisement_id: int | None,
    status: str | None,
    review_status: str | None,
    search: str | None,
) -> list[dict]:
    start_dt, end_dt = _parse_range(start_date, end_date, last_24_hours)


    return _build_report_rows(
        db=db,
        start_dt=start_dt,
        end_dt=end_dt,
        channel_id=channel_id,
        advertiser_id=advertiser_id,
        advertisement_id=advertisement_id,
        status=status,
        review_status=review_status,
        search=search,
    )


# ✅ UPDATED: Simplified headers
EXPORT_HEADERS = [
    "Date",
    "Ad Name",
    "Advertiser",
    "Start Time",
    "End Time",
    "Duration",
]


def _row_to_export_values(row: dict) -> list:
    # ✅ UPDATED: Only 6 values
    return [
        row["date"],
        row["ad_name"],
        row["advertiser"],
        row["start_time"],
        row["end_time"],
        row["duration"],
    ]


@router.get("/export/csv")
def export_csv(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    last_24_hours: bool = Query(False),
    channel_id: int | None = Query(None),
    advertiser_id: int | None = Query(None),
    advertisement_id: int | None = Query(None),
    status: str | None = Query(None),
    review_status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    rows = _export_rows(
        db,
        start_date,
        end_date,
        last_24_hours,
        channel_id,
        advertiser_id,
        advertisement_id,
        status,
        review_status,
        search,
    )


    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_HEADERS)


    for row in rows:
        writer.writerow(_row_to_export_values(row))
    buffer.seek(0)


    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dtv_detection_report.csv"},
    )


@router.get("/export/excel")
def export_excel(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    last_24_hours: bool = Query(False),
    channel_id: int | None = Query(None),
    advertiser_id: int | None = Query(None),
    advertisement_id: int | None = Query(None),
    status: str | None = Query(None),
    review_status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    rows = _export_rows(
        db,
        start_date,
        end_date,
        last_24_hours,
        channel_id,
        advertiser_id,
        advertisement_id,
        status,
        review_status,
        search,
    )


    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Detection Report"
    sheet.append(EXPORT_HEADERS)


    for row in rows:
        sheet.append(_row_to_export_values(row))


    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)


    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dtv_detection_report.xlsx"},
    )


@router.get("/export/pdf")
def export_pdf(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    last_24_hours: bool = Query(False),
    channel_id: int | None = Query(None),
    advertiser_id: int | None = Query(None),
    advertisement_id: int | None = Query(None),
    status: str | None = Query(None),
    review_status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    rows = _export_rows(
        db,
        start_date,
        end_date,
        last_24_hours,
        channel_id,
        advertiser_id,
        advertisement_id,
        status,
        review_status,
        search,
    )


    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4
    y = height - 40


    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "DTV-Ad Monitor Detection Report")
    y -= 25


    pdf.setFont("Helvetica", 9)


    for row in rows:
        # ✅ UPDATED: New PDF format
        pdf.drawString(
            40,
            y,
            f"Date: {row['date']}"
        )
        y -= 15


        pdf.drawString(
            40,
            y,
            f"Ad: {row['ad_name']}"
        )
        y -= 15


        pdf.drawString(
            40,
            y,
            f"Advertiser: {row['advertiser']}"
        )
        y -= 15


        pdf.drawString(
            40,
            y,
            f"Start: {row['start_time']}"
        )
        y -= 15


        pdf.drawString(
            40,
            y,
            f"End: {row['end_time']}"
        )
        y -= 15


        pdf.drawString(
            40,
            y,
            f"Duration: {row['duration']}s"
        )
        y -= 20


        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - 40


    pdf.save()
    buffer.seek(0)


    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=dtv_detection_report.pdf"},
    )



@router.get("/dashboard-summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    today = date.today()
    interrupted_statuses = ["interrupted", "disconnected", "error", "probe_failed"]


    return {
        "total_users": db.query(func.count(User.id)).scalar() or 0,
        "active_channels": db.query(func.count(Channel.id))
        .filter(Channel.is_active.is_(True))
        .scalar()
        or 0,
        "healthy_channels": db.query(func.count(Channel.id))
        .filter(Channel.capture_status == "healthy")
        .scalar()
        or 0,
        "interrupted_channels": db.query(func.count(Channel.id))
        .filter(Channel.capture_status.in_(interrupted_statuses))
        .scalar()
        or 0,
        "total_advertisers": db.query(func.count(Advertiser.id))
        .filter(Advertiser.is_archived.is_(False))
        .scalar()
        or 0,
        "ad_library_count": db.query(func.count(Advertisement.id)).scalar() or 0,
        "monitoring_sources": db.query(func.count(Channel.id))
        .filter(Channel.monitoring_enabled.is_(True))
        .scalar()
        or 0,
        "detections_today": db.query(func.count(AdDetectionLog.id))
        .filter(func.date(AdDetectionLog.detected_at) == today)
        .scalar()
        or 0,
        "audit_events_today": db.query(func.count(AuditLog.id))
        .filter(func.date(AuditLog.created_at) == today)
        .scalar()
        or 0,
        "evidence_items_today": db.query(func.count(DetectionEvidence.id))
        .join(AdDetectionLog, DetectionEvidence.detection_id == AdDetectionLog.id)
        .filter(func.date(AdDetectionLog.detected_at) == today)
        .scalar()
        or 0,
    }



@router.get("/audit-logs")
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()


    return [
        {
            "id": log.id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "user_email": log.user.email if log.user else None,
        }
        for log in logs
    ]



@router.get("/kpi")
def kpi(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator", "client")),
):
    total = db.query(func.count(AdDetectionLog.id)).scalar() or 0


    matched = (
        db.query(func.count(AdDetectionLog.id))
        .filter(AdDetectionLog.status == "matched")
        .scalar()
        or 0
    )


    uncertain = (
        db.query(func.count(AdDetectionLog.id))
        .filter(AdDetectionLog.status == "uncertain")
        .scalar()
        or 0
    )
    
    rejected = (
        db.query(func.count(AdDetectionLog.id))
        .filter(AdDetectionLog.review_status == "rejected")
        .scalar()
        or 0
    )


    total_duration = db.query(func.sum(AdDetectionLog.duration_seconds)).scalar() or 0


    return {
        "total": total,
        "matched": matched,
        "uncertain": uncertain,
        "rejected": rejected,
        "total_duration_seconds": total_duration,
        "match_rate": (matched / total) if total else 0,
        "uncertain_rate": (uncertain / total) if total else 0,
        "rejected_rate": (rejected / total) if total else 0,
    }