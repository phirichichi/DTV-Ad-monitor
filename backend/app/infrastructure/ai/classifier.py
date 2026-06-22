#classifier.py 
import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("dtv.classifier")

ALLOWED_CONTENT_TYPES = {"commercial", "promo", "sponsorship", "filler"}

@dataclass
class ClassificationResult:
    predicted_class: str
    confidence: float
    model_version: str
    reasoning: str

class ContentClassifier:
    """
    Rule-assisted classifier stub.

    This is intentionally structured like a production model wrapper so it can
    later be swapped with a real PyTorch or TensorFlow model while keeping the
    same interface:
    - load_model()
    - predict_segment(...)
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model_loaded = False
        self.model_version = "rule-based-v1"

    def load_model(self) -> None:
        """
        Placeholder load hook for a future ML model.
        """
        self.model_loaded = True
        logger.info("content_classifier_loaded version=%s model_path=%s", self.model_version, self.model_path)

    def _frame_features(self, frame) -> dict[str, float]:
        gray = frame if len(frame.shape) == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_brightness = float(np.mean(gray))
        height, width = gray.shape[:2]

        center_crop = gray[
            max(height // 4, 0): min((height * 3) // 4, height),
            max(width // 4, 0): min((width * 3) // 4, width),
        ]
        edge_mask = gray.copy()
        edge_mask[
            max(height // 4, 0): min((height * 3) // 4, height),
            max(width // 4, 0): min((width * 3) // 4, width),
        ] = 0

        center_mean = float(np.mean(center_crop)) if center_crop.size else mean_brightness
        edge_mean = float(np.mean(edge_mask)) if edge_mask.size else mean_brightness
        edge_to_center_ratio = edge_mean / (center_mean + 1e-6)

        return {
            "laplacian_variance": lap_var,
            "mean_brightness": mean_brightness,
            "edge_to_center_ratio": edge_to_center_ratio,
        }

    def predict_segment(
        self,
        *,
        frame,
        audio_fingerprint_available: bool,
        matched_ad_content_type: Optional[str] = None,
        expected_duration_seconds: Optional[int] = None,
        observed_duration_seconds: Optional[float] = None,
        frame_match_score: float = 0.0,
        audio_match_score: float = 0.0,
    ) -> ClassificationResult:
        if not self.model_loaded:
            self.load_model()

        features = self._frame_features(frame)
        lap_var = features["laplacian_variance"]
        brightness = features["mean_brightness"]
        edge_ratio = features["edge_to_center_ratio"]

        label_scores = {
            "commercial": 0.25,
            "promo": 0.25,
            "sponsorship": 0.25,
            "filler": 0.25,
        }

        if matched_ad_content_type in ALLOWED_CONTENT_TYPES:
            label_scores[matched_ad_content_type] += 0.35

        if frame_match_score >= 0.80 or audio_match_score >= 0.80:
            label_scores["commercial"] += 0.15

        if expected_duration_seconds is not None:
            if expected_duration_seconds <= 10:
                label_scores["sponsorship"] += 0.18
            elif expected_duration_seconds >= 25:
                label_scores["commercial"] += 0.12

        if observed_duration_seconds is not None:
            if observed_duration_seconds < 8:
                label_scores["sponsorship"] += 0.10
                label_scores["filler"] += 0.08
            elif observed_duration_seconds > 20:
                label_scores["commercial"] += 0.10

        if not audio_fingerprint_available:
            label_scores["filler"] += 0.08

        if brightness > 170:
            label_scores["promo"] += 0.05

        if lap_var < 45:
            label_scores["filler"] += 0.06

        if edge_ratio > 0.65:
            label_scores["sponsorship"] += 0.06

        best_label = max(label_scores, key=label_scores.get)
        total = sum(label_scores.values()) or 1.0
        confidence = label_scores[best_label] / total

        reasoning = (
            f"matched_type={matched_ad_content_type or 'none'}, "
            f"frame_score={frame_match_score:.4f}, "
            f"audio_score={audio_match_score:.4f}, "
            f"lap_var={lap_var:.2f}, "
            f"brightness={brightness:.2f}, "
            f"edge_ratio={edge_ratio:.4f}, "
            f"expected_duration={expected_duration_seconds}, "
            f"observed_duration={observed_duration_seconds}"
        )

        return ClassificationResult(
            predicted_class=best_label,
            confidence=round(max(0.0, min(1.0, confidence)), 6),
            model_version=self.model_version,
            reasoning=reasoning,
        )


_default_classifier: ContentClassifier | None = None


def get_classifier() -> ContentClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = ContentClassifier()
        _default_classifier.load_model()
    return _default_classifier