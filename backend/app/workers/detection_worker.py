import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.infrastructure.ai.audio_fingerprint import (
    compare_audio_fingerprints,
    generate_audio_fingerprint,
)
from app.infrastructure.ai.classifier import ClassificationResult, get_classifier
from app.infrastructure.ai.frame_hashing import compare_frame_hashes, generate_frame_hash
from app.infrastructure.monitoring.audio_extractor import extract_audio_chunk_from_stream
from app.infrastructure.monitoring.screenshot_service import save_detection_screenshot
from app.models import AdDetectionLog, Advertisement, AuditLog, Channel

logger = logging.getLogger("dtv.detection_worker")
settings = get_settings()


@dataclass
class DetectionDecision:
    matched: bool
    advertisement_id: Optional[int]
    confidence_score: float
    match_source: str
    status: str
    notes: Optional[str]
    detected_duration_seconds: Optional[int]
    predicted_content_type: Optional[str]
    classifier_confidence: float
    frame_score: float
    audio_score: float
    classifier_score: float
    watermark_score: float


@dataclass
class CandidateMatch:
    advertisement: Advertisement
    frame_score: float
    audio_score: float
    classifier_result: ClassificationResult
    classifier_alignment_score: float
    watermark_score: float
    fused_score: float
    predicted_status: str


class DetectionWorker:
    """
    HDMI-safe detection worker.

    Current production timeline behavior:
    - Uses HDMI frames from Kafka.
    - Matches frame hashes against uploaded reference videos.
    - Skips audio matching when stream_url is None.
    - Saves screenshot evidence only.
    - Clip saving is intentionally disabled until rolling HDMI buffer exists.
    """

    _rolling_observations: dict[str, deque] = defaultdict(lambda: deque(maxlen=12))

    def __init__(
        self,
        db: Session,
        frame_match_threshold: float = 0.78,
        audio_match_threshold: float = 0.75,
        hybrid_match_threshold: float = 0.72,
        duplicate_cooldown_seconds: int = 60,
        audio_chunk_duration_seconds: float = 3.0,
    ):
        self.db = db
        self.frame_match_threshold = frame_match_threshold
        self.audio_match_threshold = audio_match_threshold
        self.hybrid_match_threshold = hybrid_match_threshold
        self.duplicate_cooldown_seconds = duplicate_cooldown_seconds
        self.audio_chunk_duration_seconds = audio_chunk_duration_seconds
        self.classifier = get_classifier()

    def load_active_ads(self) -> list[Advertisement]:
        return (
            self.db.query(Advertisement)
            .options(joinedload(Advertisement.advertiser))
            .filter(Advertisement.is_active.is_(True))
            .order_by(Advertisement.created_at.desc())
            .all()
        )

    def is_duplicate_detection(self, channel_id: int, advertisement_id: int) -> bool:
        cutoff = datetime.utcnow() - timedelta(seconds=self.duplicate_cooldown_seconds)

        recent = (
            self.db.query(AdDetectionLog)
            .filter(
                AdDetectionLog.channel_id == channel_id,
                AdDetectionLog.advertisement_id == advertisement_id,
                AdDetectionLog.detected_at >= cutoff,
                AdDetectionLog.status == "matched",
            )
            .order_by(AdDetectionLog.detected_at.desc())
            .first()
        )

        return recent is not None

    def _watermark_score_placeholder(self, frame) -> float:
        _ = frame
        return 0.0

    def _classifier_alignment_score(
        self,
        ad: Advertisement,
        classification: ClassificationResult,
    ) -> float:
        if not ad.content_type:
            return classification.confidence * 0.5

        if ad.content_type == classification.predicted_class:
            return 0.75 + (classification.confidence * 0.25)

        return max(0.05, classification.confidence * 0.25)

    def _derive_primary_source(
        self,
        frame_score: float,
        audio_score: float,
        classifier_score: float,
    ) -> str:
        scores = {
            "frame": frame_score,
            "audio": audio_score,
            "classifier": classifier_score,
        }
        return max(scores, key=scores.get)

    def _estimate_detected_duration_seconds(
        self,
        *,
        stream_key: str,
        advertisement_id: int,
        sample_timestamp_seconds: float,
    ) -> int:
        observation_key = f"{stream_key}:{advertisement_id}"
        history = self._rolling_observations[observation_key]

        if not history:
            return max(int(round(self.audio_chunk_duration_seconds)), 1)

        timestamps = [float(item["timestamp_seconds"]) for item in history]

        if not timestamps:
            return max(int(round(self.audio_chunk_duration_seconds)), 1)

        estimated = (max(timestamps) - min(timestamps)) + self.audio_chunk_duration_seconds
        return max(int(round(estimated)), 1)

    def _apply_rolling_window(
        self,
        *,
        stream_key: str,
        advertisement_id: int,
        fused_score: float,
        sample_timestamp_seconds: float,
    ) -> float:
        observation_key = f"{stream_key}:{advertisement_id}"
        history = self._rolling_observations[observation_key]

        history.append(
            {
                "score": fused_score,
                "timestamp_seconds": sample_timestamp_seconds,
                "recorded_at": datetime.utcnow().isoformat(),
            }
        )

        recent_scores = [float(item["score"]) for item in history][-5:]

        if not recent_scores:
            return fused_score

        rolling_score = (fused_score * 0.5) + (
            sum(recent_scores) / len(recent_scores) * 0.5
        )

        return round(max(0.0, min(1.0, rolling_score)), 6)

    def _generate_candidate_audio_fingerprint(
        self,
        *,
        stream_url: str | None,
        timestamp_seconds: float,
    ) -> tuple[str | None, bool]:
        if not stream_url:
            logger.info("audio_fingerprint_skipped_no_stream_url")
            return None, False

        temp_audio_dir = Path(settings.temp_audio_dir)
        temp_audio_dir.mkdir(parents=True, exist_ok=True)

        tmp_audio_path = temp_audio_dir / f"sample_{int(timestamp_seconds * 1000)}.wav"

        try:
            extracted_audio_path = extract_audio_chunk_from_stream(
                stream_url=stream_url,
                output_wav_path=str(tmp_audio_path),
                duration_seconds=self.audio_chunk_duration_seconds,
            )
            candidate_audio_fingerprint = generate_audio_fingerprint(extracted_audio_path)
            return candidate_audio_fingerprint, True

        except Exception as exc:
            logger.warning("audio_fingerprint_generation_failed error=%s", str(exc))
            return None, False

        finally:
            try:
                tmp_audio_path.unlink(missing_ok=True)
            except Exception:
                logger.debug("temp_audio_cleanup_failed path=%s", tmp_audio_path)

    def _build_candidate_match(
        self,
        *,
        ad: Advertisement,
        frame,
        candidate_frame_hash: str,
        candidate_audio_fingerprint: str | None,
        audio_available: bool,
    ) -> CandidateMatch:
        frame_score = compare_frame_hashes(ad.reference_frame_hash, candidate_frame_hash)

        audio_score = compare_audio_fingerprints(
            ad.reference_audio_signature,
            candidate_audio_fingerprint,
        )

        classification = self.classifier.predict_segment(
            frame=frame,
            audio_fingerprint_available=audio_available,
            matched_ad_content_type=ad.content_type,
            expected_duration_seconds=ad.duration_seconds,
            observed_duration_seconds=self.audio_chunk_duration_seconds,
            frame_match_score=frame_score,
            audio_match_score=audio_score,
        )

        classifier_alignment_score = self._classifier_alignment_score(ad, classification)
        watermark_score = self._watermark_score_placeholder(frame)

        if audio_available:
            fused_score = (
                (frame_score * 0.40)
                + (audio_score * 0.40)
                + (classifier_alignment_score * 0.18)
                + (watermark_score * 0.02)
            )
        else:
            fused_score = (
                (frame_score * 0.78)
                + (classifier_alignment_score * 0.20)
                + (watermark_score * 0.02)
            )

        fused_score = max(0.0, min(1.0, fused_score))

        return CandidateMatch(
            advertisement=ad,
            frame_score=round(frame_score, 6),
            audio_score=round(audio_score, 6),
            classifier_result=classification,
            classifier_alignment_score=round(classifier_alignment_score, 6),
            watermark_score=round(watermark_score, 6),
            fused_score=round(fused_score, 6),
            predicted_status="matched",
        )

    def evaluate_sample(
        self,
        frame,
        stream_url: str | None,
        timestamp_seconds: float,
        ads: list[Advertisement],
        *,
        channel: Optional[Channel] = None,
    ) -> DetectionDecision:
        if not ads:
            return DetectionDecision(
                matched=False,
                advertisement_id=None,
                confidence_score=0.0,
                match_source="none",
                status="no_reference_ads",
                notes="No active advertisements available for matching",
                detected_duration_seconds=None,
                predicted_content_type=None,
                classifier_confidence=0.0,
                frame_score=0.0,
                audio_score=0.0,
                classifier_score=0.0,
                watermark_score=0.0,
            )

        candidate_frame_hash = generate_frame_hash(frame)

        candidate_audio_fingerprint, audio_available = self._generate_candidate_audio_fingerprint(
            stream_url=stream_url,
            timestamp_seconds=timestamp_seconds,
        )

        best_candidate: CandidateMatch | None = None

        for ad in ads:
            candidate = self._build_candidate_match(
                ad=ad,
                frame=frame,
                candidate_frame_hash=candidate_frame_hash,
                candidate_audio_fingerprint=candidate_audio_fingerprint,
                audio_available=audio_available,
            )

            if best_candidate is None or candidate.fused_score > best_candidate.fused_score:
                best_candidate = candidate

        if best_candidate is None:
            return DetectionDecision(
                matched=False,
                advertisement_id=None,
                confidence_score=0.0,
                match_source="none",
                status="unmatched",
                notes="No ad matched the current sample",
                detected_duration_seconds=None,
                predicted_content_type=None,
                classifier_confidence=0.0,
                frame_score=0.0,
                audio_score=0.0,
                classifier_score=0.0,
                watermark_score=0.0,
            )

        stream_key = str(channel.id) if channel else "hdmi_unknown_channel"

        rolled_score = self._apply_rolling_window(
            stream_key=stream_key,
            advertisement_id=best_candidate.advertisement.id,
            fused_score=best_candidate.fused_score,
            sample_timestamp_seconds=timestamp_seconds,
        )

        estimated_duration = self._estimate_detected_duration_seconds(
            stream_key=stream_key,
            advertisement_id=best_candidate.advertisement.id,
            sample_timestamp_seconds=timestamp_seconds,
        )

        best_source = self._derive_primary_source(
            frame_score=best_candidate.frame_score,
            audio_score=best_candidate.audio_score,
            classifier_score=best_candidate.classifier_alignment_score,
        )

        threshold = self.hybrid_match_threshold

        if not audio_available:
            threshold = self.frame_match_threshold
            best_source = "frame"

        notes = (
            f"frame_score={best_candidate.frame_score:.4f}, "
            f"audio_score={best_candidate.audio_score:.4f}, "
            f"classifier_alignment={best_candidate.classifier_alignment_score:.4f}, "
            f"classifier_predicted={best_candidate.classifier_result.predicted_class}, "
            f"classifier_confidence={best_candidate.classifier_result.confidence:.4f}, "
            f"watermark_score={best_candidate.watermark_score:.4f}, "
            f"rolling_score={rolled_score:.4f}, "
            f"audio_available={audio_available}, "
            f"clip_available=False, "
            f"classifier_reasoning={best_candidate.classifier_result.reasoning}"
        )

        if rolled_score >= threshold:
            return DetectionDecision(
                matched=True,
                advertisement_id=best_candidate.advertisement.id,
                confidence_score=rolled_score,
                match_source=best_source,
                status="matched",
                notes=notes,
                detected_duration_seconds=estimated_duration,
                predicted_content_type=best_candidate.classifier_result.predicted_class,
                classifier_confidence=best_candidate.classifier_result.confidence,
                frame_score=best_candidate.frame_score,
                audio_score=best_candidate.audio_score,
                classifier_score=best_candidate.classifier_alignment_score,
                watermark_score=best_candidate.watermark_score,
            )

        return DetectionDecision(
            matched=False,
            advertisement_id=None,
            confidence_score=rolled_score,
            match_source=best_source,
            status="uncertain",
            notes=notes,
            detected_duration_seconds=estimated_duration,
            predicted_content_type=best_candidate.classifier_result.predicted_class,
            classifier_confidence=best_candidate.classifier_result.confidence,
            frame_score=best_candidate.frame_score,
            audio_score=best_candidate.audio_score,
            classifier_score=best_candidate.classifier_alignment_score,
            watermark_score=best_candidate.watermark_score,
        )

    def _publish_live_event(self, detection: AdDetectionLog, channel: Channel) -> None:
        try:
            import redis  # type: ignore

            client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

            payload = {
                "type": "detection_created",
                "timestamp": datetime.utcnow().isoformat(),
                "detection": {
                    "id": detection.id,
                    "channel_id": detection.channel_id,
                    "channel_name": channel.name,
                    "advertisement_id": detection.advertisement_id,
                    "detected_at": detection.detected_at.isoformat()
                    if detection.detected_at
                    else None,
                    "confidence_score": detection.confidence_score,
                    "status": detection.status,
                    "duration_seconds": detection.duration_seconds,
                    "match_source": detection.match_source,
                    "review_status": detection.review_status,
                    "notes": detection.notes,
                },
            }

            client.publish("live:detections", json.dumps(payload))

        except Exception as exc:
            logger.debug("live_event_publish_skipped error=%s", str(exc))

    def persist_detection(
        self,
        channel: Channel,
        decision: DetectionDecision,
        frame,
        stream_url: str | None,
        timestamp_seconds: float,
        duration_seconds: Optional[int] = None,
    ) -> Optional[AdDetectionLog]:
        _ = stream_url
        _ = timestamp_seconds

        if not decision.matched or not decision.advertisement_id:
            return None

        if self.is_duplicate_detection(channel.id, decision.advertisement_id):
            logger.info(
                "duplicate_detection_skipped channel_id=%s advertisement_id=%s",
                channel.id,
                decision.advertisement_id,
            )
            return None

        final_duration = (
            duration_seconds
            or decision.detected_duration_seconds
            or int(round(self.audio_chunk_duration_seconds))
        )

        detection = AdDetectionLog(
    channel_id=channel.id,
    advertisement_id=decision.advertisement_id,
    detected_at=datetime.utcnow(),
    duration_seconds=final_duration,

    confidence_score=decision.confidence_score,

    audio_confidence=decision.audio_score,
    frame_confidence=decision.frame_score,

    audio_sections_matched=json.dumps(
        {
            "score": round(decision.audio_score, 4),
            "source": "audio_fingerprint",
        }
    ),

    frame_sections_matched=json.dumps(
        {
            "score": round(decision.frame_score, 4),
            "source": "frame_hash",
        }
    ),

    status=decision.status,
    match_source=decision.match_source,
    review_status="pending",
    notes=decision.notes,
)

        self.db.add(detection)
        self.db.flush()

        try:
            save_detection_screenshot(
                detection_id=detection.id,
                frame=frame,
                db=self.db,
            )
        except Exception as exc:
            logger.warning(
                "save_screenshot_failed detection_id=%s error=%s",
                detection.id,
                str(exc),
            )

        self.db.add(
            AuditLog(
                user_id=None,
                action="AUTO_DETECTION_CREATED",
                entity_type="ad_detection_log",
                entity_id=detection.id,
                details=(
                    f"Auto-detected ad_id={decision.advertisement_id} "
                    f"on channel_id={channel.id} "
                    f"with confidence={decision.confidence_score:.4f}, "
                    f"status={decision.status}, "
                    f"predicted_content_type={decision.predicted_content_type}, "
                    f"classifier_confidence={decision.classifier_confidence:.4f}, "
                    f"frame_score={decision.frame_score:.4f}, "
                    f"audio_score={decision.audio_score:.4f}, "
                    f"classifier_score={decision.classifier_score:.4f}, "
                    f"watermark_score={decision.watermark_score:.4f}, "
                    f"evidence=screenshot_only"
                ),
            )
        )

        self.db.commit()
        self.db.refresh(detection)

        self._publish_live_event(detection, channel)

        logger.info(
            "detection_persisted detection_id=%s channel_id=%s advertisement_id=%s confidence=%.4f status=%s duration=%s",
            detection.id,
            channel.id,
            decision.advertisement_id,
            decision.confidence_score,
            decision.status,
            final_duration,
        )

        return detection