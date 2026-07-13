#backend/app/workers/ingestion_worker.py
import base64
import logging
import threading
import time
from datetime import datetime, timezone
import cv2
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.messaging.kafka_producer import KafkaJSONProducer
from app.infrastructure.monitoring.frame_extractor import preprocess_frame, should_sample_frame
from app.infrastructure.monitoring.stream_ingestor import StreamIngestor
from app.models import AuditLog, Channel

logger = logging.getLogger("dtv.ingestion_worker")
settings = get_settings()

class IngestionWorker:
    """
    HDMI-only ingestion producer.
    Responsibilities:
    - fetch monitoring-enabled HDMI channels
    - open HDMI capture card independently per channel
    - sample and preprocess frames
    - publish frame events to Kafka
    - update channel health and interruption status
    """

    def __init__(
        self,
        frame_sample_every_seconds: float | None = None,
        preprocess_resize_width: int | None = None,
        preprocess_grayscale: bool | None = None,
        idle_sleep_seconds: float | None = None,
        kafka_topic: str | None = None,
    ):
        self.frame_sample_every_seconds = (
            frame_sample_every_seconds or settings.frame_sample_interval_seconds
        )
        self.preprocess_resize_width = preprocess_resize_width or settings.frame_resize_width
        self.preprocess_grayscale = (
            settings.preprocess_grayscale if preprocess_grayscale is None else preprocess_grayscale
        )
        self.idle_sleep_seconds = idle_sleep_seconds or settings.worker_idle_sleep_seconds
        self.kafka_topic = kafka_topic or getattr(settings, "kafka_frames_topic", "dtv.sampled.frames")
        self.running_threads: dict[int, threading.Thread] = {}
        self.stop_flags: dict[int, bool] = {}

    def fetch_monitoring_channels(self, db: Session) -> list[Channel]:
        return (
            db.query(Channel)
            .filter(Channel.monitoring_enabled.is_(True), Channel.is_active.is_(True))
            .order_by(Channel.main_channel_flag.desc(), Channel.created_at.desc())
            .all()
        )

    def _update_channel_health(
        self,
        *,
        db: Session,
        channel_id: int,
        capture_status: str,
        interruption_reason: str | None = None,
        audit_details: str | None = None,
    ) -> None:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            return

        now = datetime.now(timezone.utc)
        channel.last_heartbeat_at = now
        channel.capture_status = capture_status

        if capture_status in {"interrupted", "error", "disconnected", "source_config_error"}:
            channel.last_interruption_at = now
            channel.last_interruption_reason = interruption_reason or capture_status

        if audit_details:
            db.add(
                AuditLog(
                    user_id=None,
                    action="HDMI_CHANNEL_HEALTH_UPDATED",
                    entity_type="channel",
                    entity_id=channel.id,
                    details=audit_details,
                )
            )
        db.commit()

    def _encode_frame(self, frame) -> str:
        success, encoded = cv2.imencode(".jpg", frame)
        if not success:
            raise RuntimeError("Failed to encode HDMI frame for Kafka event")
        return base64.b64encode(encoded.tobytes()).decode("utf-8")

    def process_channel(self, channel_id: int) -> None:
        producer = KafkaJSONProducer(client_id=f"dtv-hdmi-ingestion-producer-{channel_id}")
        try:
            while not self.stop_flags.get(channel_id, False):
                with SessionLocal() as db:
                    channel = db.query(Channel).filter(Channel.id == channel_id).first()

                    if not channel:
                        logger.warning("channel_not_found channel_id=%s", channel_id)
                        return

                    if not channel.monitoring_enabled or not channel.is_active:
                        logger.info("channel_not_active_or_not_monitored channel_id=%s", channel_id)
                        return

                    if not channel.input_identifier:
                        logger.warning("hdmi_channel_missing_input_identifier channel_id=%s", channel.id)
                        self._update_channel_health(
                            db=db,
                            channel_id=channel.id,
                            capture_status="source_config_error",
                            interruption_reason="Missing HDMI input_identifier",
                            audit_details="HDMI input identifier is missing",
                        )
                        time.sleep(self.idle_sleep_seconds)
                        continue

                    ingestor = StreamIngestor(
                        input_identifier=channel.input_identifier,
                        channel_id=channel.id,
                        source_id=channel.input_identifier,
                        reconnect_delay_seconds=settings.stream_reconnect_delay_seconds,
                        max_retries=settings.stream_max_retries,
                    )

                    published_count = 0
                    dropped_count = 0
                    last_heartbeat_touch = time.time()

                    try:
                        logger.info(
                            "starting_hdmi_ingestion channel_id=%s name=%s input_identifier=%s",
                            channel.id,
                            channel.name,
                            channel.input_identifier,
                        )

                        for stream_frame in ingestor.frame_generator():
                            if self.stop_flags.get(channel_id, False):
                                break

                            try:
                                if not should_sample_frame(
                                    frame_index=stream_frame.frame_index,
                                    fps=stream_frame.fps,
                                    sample_every_seconds=self.frame_sample_every_seconds,
                                ):
                                    continue

                                processed_frame = preprocess_frame(
                                    frame=stream_frame.frame,
                                    resize_width=self.preprocess_resize_width,
                                    grayscale=self.preprocess_grayscale,
                                )

                                payload = {
                                    "channel_id": channel.id,
                                    "channel_name": channel.name,
                                    "input_identifier": channel.input_identifier,
                                    "capture_card_name": channel.capture_card_name,
                                    "frame_index": stream_frame.frame_index,
                                    "fps": stream_frame.fps,
                                    "timestamp_seconds": stream_frame.timestamp_seconds,
                                    "ingest_wallclock_utc": stream_frame.ingest_wallclock_utc,
                                    "source_wallclock_utc": stream_frame.source_wallclock_utc,
                                    "retry_count": stream_frame.retry_count,
                                    "frame_jpeg_b64": self._encode_frame(processed_frame),
                                }

                                producer.publish(
                                    topic=self.kafka_topic,
                                    payload=payload,
                                    key=str(channel.id),
                                )

                                published_count += 1
                                now = time.time()
                                if now - last_heartbeat_touch >= 10:
                                    self._update_channel_health(
                                        db=db,
                                        channel_id=channel.id,
                                        capture_status="healthy",
                                    )
                                    last_heartbeat_touch = now

                                if published_count % 50 == 0:
                                    logger.info(
                                        "hdmi_channel_publish_progress channel_id=%s published=%s dropped=%s",
                                        channel.id,
                                        published_count,
                                        dropped_count,
                                    )

                            except Exception as exc:
                                dropped_count += 1
                                logger.exception(
                                    "hdmi_frame_publish_error channel_id=%s frame_index=%s dropped=%s error=%s",
                                    channel.id,
                                    stream_frame.frame_index,
                                    dropped_count,
                                    str(exc),
                                )

                    except Exception as exc:
                        logger.exception(
                            "hdmi_ingestion_loop_error channel_id=%s error=%s",
                            channel.id,
                            str(exc),
                        )
                        self._update_channel_health(
                            db=db,
                            channel_id=channel.id,
                            capture_status="interrupted",
                            interruption_reason=str(exc),
                            audit_details=f"HDMI ingestion interrupted: {str(exc)}",
                        )
                        time.sleep(self.idle_sleep_seconds)

        finally:
            producer.close()
    def _start_channel_thread(self, channel_id: int) -> None:
        if channel_id in self.running_threads and self.running_threads[channel_id].is_alive():
            return

        self.stop_flags[channel_id] = False
        thread = threading.Thread(
            target=self.process_channel,
            args=(channel_id,),
            daemon=True,
            name=f"hdmi-ingestion-channel-{channel_id}",
        )

        self.running_threads[channel_id] = thread
        thread.start()
        logger.info("hdmi_channel_thread_started channel_id=%s", channel_id)

    def _stop_channel_thread(self, channel_id: int) -> None:
        if channel_id in self.stop_flags:
            self.stop_flags[channel_id] = True
            logger.info("hdmi_channel_thread_stop_requested channel_id=%s", channel_id)

    def run_forever(self) -> None:
        logger.info("hdmi_ingestion_worker_started")

        while True:
            try:
                with SessionLocal() as db:
                    channels = self.fetch_monitoring_channels(db)
                    active_ids = {channel.id for channel in channels}

                if not channels:
                    logger.info("no_monitoring_enabled_hdmi_channels")
                    time.sleep(self.idle_sleep_seconds)
                    continue

                for channel in channels:
                    self._start_channel_thread(channel.id)

                for known_channel_id in list(self.running_threads.keys()):
                    if known_channel_id not in active_ids:
                        self._stop_channel_thread(known_channel_id)

            except Exception as exc:
                logger.exception("hdmi_ingestion_worker_supervisor_error error=%s", str(exc))
            time.sleep(self.idle_sleep_seconds)

if __name__ == "__main__":
    worker = IngestionWorker()
    worker.run_forever()