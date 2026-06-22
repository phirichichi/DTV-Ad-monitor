#frame_extractor.py 
import logging
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("dtv.frame_extractor")

LAST_FRAME: Optional[np.ndarray] = None


def should_sample_frame(
    frame_index: int,
    fps: float,
    sample_every_seconds: float,
) -> bool:
    if fps <= 0:
        return frame_index % max(int(sample_every_seconds), 1) == 0

    sample_interval_frames = max(int(fps * sample_every_seconds), 1)
    return frame_index % sample_interval_frames == 0


def detect_scene_change(frame, threshold: float = 0.30) -> bool:
    """
    Detect whether the current frame is significantly different from the previous one.
    """
    global LAST_FRAME

    if frame is None:
        return False

    if LAST_FRAME is None:
        LAST_FRAME = frame.copy()
        return True

    previous = LAST_FRAME
    if previous.shape != frame.shape:
        previous = cv2.resize(previous, (frame.shape[1], frame.shape[0]))

    diff = cv2.absdiff(previous, frame)
    score = float(np.mean(diff) / 255.0)

    LAST_FRAME = frame.copy()
    return score > threshold


def extract_roi(
    frame,
    roi: Optional[Tuple[int, int, int, int]] = None,
):
    """
    Extract a region of interest from the frame.
    roi = (x, y, w, h)
    """
    if frame is None:
        raise RuntimeError("Frame is None")

    if not roi:
        return frame

    x, y, w, h = roi
    return frame[y:y + h, x:x + w]


def extract_watermark_roi(frame):
    """
    Placeholder region for logo/watermark analysis.
    Uses the top-right corner where TV station bugs commonly appear.
    """
    if frame is None:
        raise RuntimeError("Frame is None")

    height, width = frame.shape[:2]
    roi_width = max(int(width * 0.20), 1)
    roi_height = max(int(height * 0.20), 1)

    x = width - roi_width
    y = 0

    return extract_roi(frame, (x, y, roi_width, roi_height))


def _to_grayscale(frame) -> np.ndarray:
    if len(frame.shape) == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def compute_average_hash(frame, hash_size: int = 8) -> str:
    """
    Simple average hash (aHash).
    """
    gray = _to_grayscale(frame)
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    avg = resized.mean()
    bits = resized > avg
    return "".join("1" if bit else "0" for bit in bits.flatten())


def compute_difference_hash(frame, hash_size: int = 8) -> str:
    """
    Difference hash (dHash).
    """
    gray = _to_grayscale(frame)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    return "".join("1" if bit else "0" for bit in diff.flatten())


def compute_perceptual_hash(frame, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """
    Perceptual hash (pHash) implemented without external imagehash dependency.
    """
    gray = _to_grayscale(frame)
    size = hash_size * highfreq_factor

    resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    resized = np.float32(resized)

    dct = cv2.dct(resized)
    dct_low_freq = dct[:hash_size, :hash_size]

    median = np.median(dct_low_freq[1:, 1:])
    bits = dct_low_freq > median

    return "".join("1" if bit else "0" for bit in bits.flatten())


def compute_multi_hashes(frame) -> dict[str, str]:
    """
    Generate multiple hashes for stronger comparison later.
    """
    return {
        "ahash": compute_average_hash(frame),
        "dhash": compute_difference_hash(frame),
        "phash": compute_perceptual_hash(frame),
    }


def preprocess_frame(
    frame,
    resize_width: Optional[int] = 320,
    grayscale: bool = False,
):
    if frame is None:
        raise RuntimeError("Frame is None")

    processed = frame

    if resize_width and resize_width > 0:
        height, width = processed.shape[:2]
        if width > 0:
            ratio = resize_width / float(width)
            resize_height = max(int(height * ratio), 1)
            processed = cv2.resize(processed, (resize_width, resize_height))

    if grayscale:
        processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)

    return processed


def save_frame_image(frame, file_path: str) -> str:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    success = cv2.imwrite(str(path), frame)
    if not success:
        raise RuntimeError(f"Failed to save frame image to {file_path}")

    logger.info("frame_saved path=%s", file_path)
    return str(path)