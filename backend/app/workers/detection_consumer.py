import base64
import logging
import cv2
import numpy as np

from app.core.config import get_settings
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.messaging.kafka_consumer import KafkaJSONConsumer
from app.models import Channel
from app.workers.detection_worker import DetectionWorker

logger = logging.getLogger("dtv.detection_consumer")
settings = get_settings()

class DetectionConsumerWorker:
    def __init__(
        self,
        topic: str | None = None,
        group_id: str = "dtv-detection-consumers",
    ):
        self.topic = topic or getattr(settings, "kafka_frames_topic", "dtv.sampled.frames")
        self.group_id = group_id

    def _decode_frame(self, frame_jpeg_b64: str):
        raw = base64.b64decode(frame_jpeg_b64.encode("utf-8"))
        np_buf = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Failed to decode Kafka frame")
        return frame

    def run_forever(self) -> None:
        logger.info(
            "detection_consumer_started topic=%s group_id=%s",
            self.topic,
            self.group_id,
        )

        consumer = KafkaJSONConsumer(topic=self.topic, group_id=self.group_id)
        try:
            for payload in consumer.iter_messages():
                try:
                    frame = self._decode_frame(payload["frame_jpeg_b64"])
                    channel_id = int(payload["channel_id"])
                    timestamp_seconds = float(payload["timestamp_seconds"])

                    with SessionLocal() as db:
                        channel = db.query(Channel).filter(Channel.id == channel_id).first()
                        if not channel:
                            logger.warning("consumer_channel_not_found channel_id=%s", channel_id)
                            continue
                        detection_worker = DetectionWorker(db=db)
                        ads = detection_worker.load_active_ads()
                        decision = detection_worker.evaluate_sample(
                            frame=frame,
                            stream_url=None,
                            timestamp_seconds=timestamp_seconds,
                            ads=ads,
                            channel=channel,
                        )

                        if decision.matched:
                            detection_worker.persist_detection(
                                channel=channel,
                                decision=decision,
                                frame=frame,
                                stream_url=None,
                                timestamp_seconds=timestamp_seconds,
                                duration_seconds=decision.detected_duration_seconds,
                            )
                        else:
                            logger.debug(
                                "consumer_no_match channel_id=%s status=%s confidence=%s",
                                channel_id,
                                decision.status,
                                decision.confidence_score,
                            )

                except Exception as exc:
                    logger.exception("consumer_message_processing_error error=%s", str(exc))
        finally:
            consumer.close()
if __name__ == "__main__":
    worker = DetectionConsumerWorker()
    worker.run_forever()