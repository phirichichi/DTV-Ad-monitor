import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AdDetectionLog,
    DailyReport,
)

logger = logging.getLogger("dtv.reconciliation_worker")


class ReconciliationWorker:
    """
    Reconciles detection data and stores daily summaries.
    """

    def __init__(self, db: Session):
        self.db = db

    def reconcile_daily(self) -> DailyReport:
        today = date.today()

        start_time = datetime.combine(today, datetime.min.time())
        end_time = start_time + timedelta(days=1)

        total_detections = (
            self.db.query(func.count(AdDetectionLog.id))
            .filter(
                AdDetectionLog.detected_at >= start_time,
                AdDetectionLog.detected_at < end_time,
            )
            .scalar()
            or 0
        )

        avg_audio_confidence = (
            self.db.query(func.avg(AdDetectionLog.audio_confidence))
            .filter(
                AdDetectionLog.detected_at >= start_time,
                AdDetectionLog.detected_at < end_time,
            )
            .scalar()
            or 0
        )

        avg_frame_confidence = (
            self.db.query(func.avg(AdDetectionLog.frame_confidence))
            .filter(
                AdDetectionLog.detected_at >= start_time,
                AdDetectionLog.detected_at < end_time,
            )
            .scalar()
            or 0
        )

        notes = (
            f"Average Audio Confidence={float(avg_audio_confidence):.4f}, "
            f"Average Frame Confidence={float(avg_frame_confidence):.4f}"
        )

        report = (
            self.db.query(DailyReport)
            .filter(DailyReport.report_date == today)
            .first()
        )

        if report:
            report.total_detections = total_detections
            report.notes = notes
        else:
            report = DailyReport(
                report_date=today,
                total_detections=total_detections,
                notes=notes,
            )
            self.db.add(report)

        self.db.commit()
        self.db.refresh(report)

        logger.info(
            "daily_reconciliation_complete date=%s detections=%s",
            today,
            total_detections,
        )

        return report