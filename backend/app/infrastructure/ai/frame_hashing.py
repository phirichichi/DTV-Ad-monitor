#frame_hashing.py 
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger("dtv.frame_hashing")


HASH_SIZE = 8


@dataclass
class FrameHashPayload:
    version: str
    hashes: list[str]
    descriptors: list[str]


def _ensure_grayscale(frame) -> np.ndarray:
    if frame is None:
        raise RuntimeError("Frame is None")
    if len(frame.shape) == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _phash(image: np.ndarray, hash_size: int = HASH_SIZE, highfreq_factor: int = 4) -> str:
    grayscale = _ensure_grayscale(image)
    resized = cv2.resize(
        grayscale,
        (hash_size * highfreq_factor, hash_size * highfreq_factor),
        interpolation=cv2.INTER_AREA,
    )
    resized = np.float32(resized)
    dct = cv2.dct(resized)
    dct_lowfreq = dct[:hash_size, :hash_size]
    median = np.median(dct_lowfreq[1:, 1:])
    bits = dct_lowfreq > median
    return "".join("1" if bit else "0" for bit in bits.flatten())


def _crop_center(frame, ratio: float = 0.6):
    height, width = frame.shape[:2]
    crop_h = max(int(height * ratio), 1)
    crop_w = max(int(width * ratio), 1)
    start_y = max((height - crop_h) // 2, 0)
    start_x = max((width - crop_w) // 2, 0)
    return frame[start_y:start_y + crop_h, start_x:start_x + crop_w]


def _crop_top_without_bug(frame, keep_ratio: float = 0.85):
    """
    Keeps most of the frame while trimming a small top-right area where station
    logos or bugs often live.
    """
    height, width = frame.shape[:2]
    cut_h = max(int(height * keep_ratio), 1)
    cut_w = max(int(width * keep_ratio), 1)
    return frame[:cut_h, :cut_w]


def generate_frame_hash(frame) -> str:
    """
    Generate a multi-view perceptual hash payload.

    Stores multiple hashes so matching is more tolerant to:
    - compression,
    - scaling,
    - overlays,
    - slight color changes,
    - station logo placement.
    """
    full_hash = _phash(frame)
    center_hash = _phash(_crop_center(frame))
    trimmed_hash = _phash(_crop_top_without_bug(frame))

    payload = FrameHashPayload(
        version="frame-phash-v2",
        hashes=[full_hash, center_hash, trimmed_hash],
        descriptors=["full", "center", "trimmed"],
    )
    return json.dumps(asdict(payload), separators=(",", ":"))


def _safe_parse_hash(value: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        logger.warning("invalid_frame_hash_json")
        return None


def _hamming_similarity(hash_a: str, hash_b: str) -> float:
    if not hash_a or not hash_b:
        return 0.0

    max_len = max(len(hash_a), len(hash_b))
    padded_a = hash_a.ljust(max_len, "0")
    padded_b = hash_b.ljust(max_len, "0")

    distance = sum(1 for a, b in zip(padded_a, padded_b) if a != b)
    return max(0.0, 1.0 - (distance / max_len))


def compare_frame_hashes(
    reference_hash: str | dict[str, Any] | None,
    candidate_hash: str | dict[str, Any] | None,
) -> float:
    """
    Compare perceptual frame hash payloads and return a score in [0, 1].

    Uses best-match across stored views to improve resilience.
    """
    reference = _safe_parse_hash(reference_hash)
    candidate = _safe_parse_hash(candidate_hash)

    if not reference or not candidate:
        return 0.0

    reference_hashes = reference.get("hashes", []) or []
    candidate_hashes = candidate.get("hashes", []) or []

    if not reference_hashes or not candidate_hashes:
        return 0.0

    best_score = 0.0
    for ref_hash in reference_hashes:
        for cand_hash in candidate_hashes:
            score = _hamming_similarity(ref_hash, cand_hash)
            if score > best_score:
                best_score = score

    return round(best_score, 6)