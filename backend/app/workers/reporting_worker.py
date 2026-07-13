import logging
import time
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.db.session import SessionLocal
from app.models import (
    AdDetectionLog,
    Advertisement,
    Advertiser,
    Channel,
    DailyReport,
)

logger = logging.getLogger("dtv.reporting_worker")

class ReportingWorker:
    """
    Lightweight reporting worker.

    This worker does not handle playlist compliance.
    It only summarizes detected ads, advertiser activity, HDMI input activity,
    and capture interruptions.
    """

    def __init__(self, loop_sleep_seconds: int = 3600):
        self.loop_sleep_seconds = loop_sleep_seconds

    def run_hourly(self, db: Session) -> None:
        last_hour = datetime.utcnow() - timedelta(hours=1)
        total_detections = (
            db.query(func.count(AdDetectionLog.id))
            .filter(AdDetectionLog.detected_at >= last_hour)
            .scalar()
            or 0
        )

        avg_confidence = (
            db.query(func.avg(AdDetectionLog.confidence_score))
            .filter(AdDetectionLog.detected_at >= last_hour)
            .scalar()
            or 0
        )

        interrupted_inputs = (
            db.query(func.count(Channel.id))
            .filter(
                Channel.capture_status.in_(
                    ["interrupted", "disconnected", "error", "probe_failed"]
                )
            )
            .scalar()
            or 0
        )

        logger.info(
           "hourly_reporting total_detections=%s avg_confidence=%s interrupted_inputs=%s",
            total_detections,
            float(avg_confidence or 0),
            interrupted_inputs,
        )

    def run_daily(self, db: Session) -> None:
        last_24_hours = datetime.utcnow() - timedelta(days=1)
        ad_results = (
            db.query(
                Advertisement.id,
                Advertisement.title,
                func.count(AdDetectionLog.id).label("detection_count"),
                func.sum(AdDetectionLog.duration_seconds).label("total_duration"),
                func.avg(AdDetectionLog.confidence_score).label("avg_confidence"),
                func.avg(AdDetectionLog.audio_confidence).label("avg_audio_confidence"),
                func.avg(AdDetectionLog.frame_confidence).label("avg_frame_confidence"),
            )
            .join(AdDetectionLog, AdDetectionLog.advertisement_id == Advertisement.id)
            .filter(AdDetectionLog.detected_at >= last_24_hours)
            .group_by(Advertisement.id, Advertisement.title)
            .all()
        )

        advertiser_results = (
            db.query(
                Advertiser.id,
                Advertiser.name,
                func.count(AdDetectionLog.id).label("detection_count"),
            )
            .join(Advertisement, Advertisement.advertiser_id == Advertiser.id)
            .join(AdDetectionLog, AdDetectionLog.advertisement_id == Advertisement.id)
            .filter(AdDetectionLog.detected_at >= last_24_hours)
            .group_by(Advertiser.id, Advertiser.name)
            .all()
        )

        detection_counts_subquery = (
            db.query(
                AdDetectionLog.channel_id.label("channel_id"),
                func.count(AdDetectionLog.id).label("detection_count"),
            )
            .filter(AdDetectionLog.detected_at >= last_24_hours)
            .group_by(AdDetectionLog.channel_id)
            .subquery()
        )

        channel_results = (
            db.query(
                Channel.id,
                Channel.name,
                Channel.capture_status,
                Channel.last_interruption_at,
                Channel.last_interruption_reason,
                func.coalesce(detection_counts_subquery.c.detection_count, 0).label(
                    "detection_count"
                ),
            )
            .outerjoin(
                detection_counts_subquery,
                detection_counts_subquery.c.channel_id == Channel.id,
            )
            .order_by(Channel.created_at.desc())
            .all()
        )

        for (
            ad_id,
            title,
            count,
            duration,
            avg_confidence,
            avg_audio_confidence,
            avg_frame_confidence,
        ) in ad_results:
            logger.info(
                "daily_ad_kpi "
                "ad_id=%s "
                "title=%s "
                "detections=%s "
                "duration=%s "
                "avg_confidence=%s "
                "avg_audio_confidence=%s "
                "avg_frame_confidence=%s",
                ad_id,
                title,
                count,
                duration or 0,
                float(avg_confidence or 0),
                float(avg_audio_confidence or 0),
                float(avg_frame_confidence or 0),
            )
        for advertiser_id, name, count in advertiser_results:
            logger.info(
                "daily_advertiser_kpi advertiser_id=%s name=%s detections=%s",
                advertiser_id,
                name,
                count,
            )
        for (
            channel_id,
            name,
            capture_status,
            last_interruption_at,
            last_interruption_reason,
            count,
        ) in channel_results:
            logger.info(
                "daily_channel_kpi channel_id=%s name=%s detections=%s capture_status=%s interruption_time=%s interruption_reason=%s",
                channel_id,
                name,
                count,
                capture_status,
                last_interruption_at.isoformat() if last_interruption_at else None,
                last_interruption_reason,
            )

        # ✅ Add DailyReport Generation
        daily_detection_total = (
            db.query(func.count(AdDetectionLog.id))
            .filter(AdDetectionLog.detected_at >= last_24_hours)
            .scalar()
            or 0
        )
        today = datetime.utcnow().date()
        existing_report = (
            db.query(DailyReport)
            .filter(DailyReport.report_date == today)
            .first()
        )

        report_notes = (
            f"Generated automatically. "
            f"Total detections={daily_detection_total}"
        )

        if existing_report:
            existing_report.total_detections = daily_detection_total
            existing_report.notes = report_notes
        else:
            db.add(
                DailyReport(
                    report_date=today,
                    total_detections=daily_detection_total,
                    notes=report_notes,
                )
            )
        db.commit()

    def run_forever(self) -> None:
        logger.info("reporting_worker_started")
        while True:
            try:
                with SessionLocal() as db:
                    self.run_hourly(db)
                    self.run_daily(db)
            except Exception as exc:
                logger.exception("reporting_worker_error error=%s", str(exc))
            time.sleep(self.loop_sleep_seconds)
if __name__ == "__main__":
    worker = ReportingWorker()
    worker.run_forever()