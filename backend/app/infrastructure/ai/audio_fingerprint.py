#audio_fingerprint.py 
import json
import logging
import math
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("dtv.audio_fingerprint")

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_WINDOW_SECONDS = 1.5
DEFAULT_HOP_SECONDS = 0.5
DEFAULT_N_FFT = 2048
DEFAULT_HOP_LENGTH = 512
DEFAULT_NUM_BANDS = 32

@dataclass
class AudioFingerprintPayload:
    version: str
    sample_rate: int
    duration_seconds: float
    windows: list[list[int]]
    band_peaks: list[list[int]]
    energy_profile: list[float]

def _load_wav_mono(audio_file_path: str) -> tuple[np.ndarray, int]:
    path = Path(audio_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    with wave.open(str(path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        num_channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        num_frames = wav_file.getnframes()

        raw = wav_file.readframes(num_frames)

    dtype_map = {
        1: np.int8,
        2: np.int16,
        4: np.int32,
    }
    if sample_width not in dtype_map:
        raise RuntimeError(f"Unsupported WAV sample width: {sample_width}")

    samples = np.frombuffer(raw, dtype=dtype_map[sample_width]).astype(np.float32)

    if num_channels > 1:
        samples = samples.reshape(-1, num_channels).mean(axis=1)

    max_abs = np.max(np.abs(samples)) if samples.size else 0.0
    if max_abs > 0:
        samples = samples / max_abs

    return samples, sample_rate

def _resample_if_needed(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or samples.size == 0:
        return samples

    duration = len(samples) / float(source_rate)
    old_times = np.linspace(0.0, duration, num=len(samples), endpoint=False)
    new_length = max(int(duration * target_rate), 1)
    new_times = np.linspace(0.0, duration, num=new_length, endpoint=False)

    return np.interp(new_times, old_times, samples).astype(np.float32)

def _frame_signal(samples: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    if samples.size < frame_length:
        padding = frame_length - samples.size
        samples = np.pad(samples, (0, padding))

    num_frames = 1 + max((len(samples) - frame_length) // hop_length, 0)
    if num_frames <= 0:
        num_frames = 1

    frames = []
    for start in range(0, len(samples) - frame_length + 1, hop_length):
        frames.append(samples[start:start + frame_length])

    if not frames:
        frames = [np.pad(samples, (0, max(frame_length - len(samples), 0)))[:frame_length]]

    return np.stack(frames, axis=0)

def _spectrogram(samples: np.ndarray, n_fft: int, hop_length: int) -> np.ndarray:
    frames = _frame_signal(samples, n_fft, hop_length)
    window = np.hanning(n_fft).astype(np.float32)
    windowed = frames * window
    spectrum = np.fft.rfft(windowed, axis=1)
    magnitude = np.abs(spectrum)
    return magnitude.T


def _compress_into_bands(spectrogram: np.ndarray, num_bands: int) -> np.ndarray:
    freq_bins, time_bins = spectrogram.shape
    if freq_bins <= num_bands:
        padded = np.zeros((num_bands, time_bins), dtype=np.float32)
        padded[:freq_bins, :] = spectrogram
        return padded

    indices = np.linspace(0, freq_bins, num_bands + 1, dtype=int)
    bands = []
    for band_idx in range(num_bands):
        start = indices[band_idx]
        end = max(indices[band_idx + 1], start + 1)
        bands.append(np.mean(spectrogram[start:end, :], axis=0))
    return np.stack(bands, axis=0)

def _window_band_signature(
    band_matrix: np.ndarray,
    sample_rate: int,
    hop_length: int,
    window_seconds: float,
    hop_seconds: float,
) -> tuple[list[list[int]], list[list[int]], list[float]]:
    frames_per_window = max(int((window_seconds * sample_rate) / hop_length), 1)
    frames_per_hop = max(int((hop_seconds * sample_rate) / hop_length), 1)

    num_bands, num_frames = band_matrix.shape
    signatures: list[list[int]] = []
    peak_indices: list[list[int]] = []
    energy_profile: list[float] = []

    for start in range(0, max(num_frames - frames_per_window + 1, 1), frames_per_hop):
        end = min(start + frames_per_window, num_frames)
        chunk = band_matrix[:, start:end]

        if chunk.size == 0:
            continue

        band_energy = np.mean(chunk, axis=1)
        energy_profile.append(float(np.mean(band_energy)))

        normalized = band_energy / (np.max(band_energy) + 1e-8)
        quantized = np.clip(np.round(normalized * 15), 0, 15).astype(int).tolist()

        strongest = np.argsort(band_energy)[-5:]
        peak_indices.append(sorted(int(x) for x in strongest.tolist()))
        signatures.append(quantized)

    if not signatures:
        band_energy = np.mean(band_matrix, axis=1)
        normalized = band_energy / (np.max(band_energy) + 1e-8)
        signatures.append(np.clip(np.round(normalized * 15), 0, 15).astype(int).tolist())
        strongest = np.argsort(band_energy)[-5:]
        peak_indices.append(sorted(int(x) for x in strongest.tolist()))
        energy_profile.append(float(np.mean(band_energy)))

    return signatures, peak_indices, energy_profile

def generate_audio_fingerprint(
    audio_file_path: str,
    *,
    target_sample_rate: int = DEFAULT_SAMPLE_RATE,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    hop_seconds: float = DEFAULT_HOP_SECONDS,
    n_fft: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
    num_bands: int = DEFAULT_NUM_BANDS,
) -> str:
    """
    Generate a robust JSON audio fingerprint using band-energy windows.

    This is far stronger than the previous SHA256-bytes placeholder because it:
    - normalizes signal energy,
    - uses spectral band signatures rather than raw bytes,
    - supports multiple overlapping windows,
    - tolerates some offset and compression changes.
    """
    samples, sample_rate = _load_wav_mono(audio_file_path)
    samples = _resample_if_needed(samples, sample_rate, target_sample_rate)

    if samples.size == 0:
        payload = AudioFingerprintPayload(
            version="audio-fingerprint-v2",
            sample_rate=target_sample_rate,
            duration_seconds=0.0,
            windows=[],
            band_peaks=[],
            energy_profile=[],
        )
        return json.dumps(asdict(payload), separators=(",", ":"))

    spectrogram = _spectrogram(samples, n_fft=n_fft, hop_length=hop_length)
    band_matrix = _compress_into_bands(spectrogram, num_bands=num_bands)
    windows, band_peaks, energy_profile = _window_band_signature(
        band_matrix=band_matrix,
        sample_rate=target_sample_rate,
        hop_length=hop_length,
        window_seconds=window_seconds,
        hop_seconds=hop_seconds,
    )

    payload = AudioFingerprintPayload(
        version="audio-fingerprint-v2",
        sample_rate=target_sample_rate,
        duration_seconds=round(len(samples) / float(target_sample_rate), 4),
        windows=windows,
        band_peaks=band_peaks,
        energy_profile=[round(float(x), 6) for x in energy_profile],
    )
    return json.dumps(asdict(payload), separators=(",", ":"))


def _safe_parse_fingerprint(value: str | dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        logger.warning("invalid_audio_fingerprint_json")
        return None

def _window_similarity(reference_window: list[int], candidate_window: list[int]) -> float:
    if not reference_window or not candidate_window:
        return 0.0

    max_len = max(len(reference_window), len(candidate_window))
    ref = reference_window + [0] * (max_len - len(reference_window))
    cand = candidate_window + [0] * (max_len - len(candidate_window))

    diffs = [abs(a - b) for a, b in zip(ref, cand)]
    mean_diff = float(np.mean(diffs)) if diffs else 15.0
    return max(0.0, 1.0 - (mean_diff / 15.0))

def _peak_overlap_score(reference_peaks: list[int], candidate_peaks: list[int]) -> float:
    if not reference_peaks or not candidate_peaks:
        return 0.0
    ref_set = set(reference_peaks)
    cand_set = set(candidate_peaks)
    intersection = len(ref_set & cand_set)
    union = max(len(ref_set | cand_set), 1)
    return intersection / union

def compare_audio_fingerprints(
    reference_fingerprint: str | dict[str, Any] | None,
    candidate_fingerprint: str | dict[str, Any] | None,
) -> float:
    """
    Compare two JSON audio fingerprints and return a similarity score in [0, 1].

    Matching is offset-tolerant: each candidate window is allowed to align against
    the best reference window.
    """
    reference = _safe_parse_fingerprint(reference_fingerprint)
    candidate = _safe_parse_fingerprint(candidate_fingerprint)

    if not reference or not candidate:
        return 0.0

    reference_windows = reference.get("windows", []) or []
    candidate_windows = candidate.get("windows", []) or []
    reference_peaks = reference.get("band_peaks", []) or []
    candidate_peaks = candidate.get("band_peaks", []) or []

    if not reference_windows or not candidate_windows:
        return 0.0

    match_scores: list[float] = []

    for candidate_idx, candidate_window in enumerate(candidate_windows):
        best_for_candidate = 0.0
        candidate_peak = candidate_peaks[candidate_idx] if candidate_idx < len(candidate_peaks) else []

        for ref_idx, reference_window in enumerate(reference_windows):
            reference_peak = reference_peaks[ref_idx] if ref_idx < len(reference_peaks) else []
            signature_score = _window_similarity(reference_window, candidate_window)
            peak_score = _peak_overlap_score(reference_peak, candidate_peak)
            combined = (signature_score * 0.8) + (peak_score * 0.2)
            if combined > best_for_candidate:
                best_for_candidate = combined

        match_scores.append(best_for_candidate)

    if not match_scores:
        return 0.0

    top_matches = sorted(match_scores, reverse=True)[: max(1, math.ceil(len(match_scores) * 0.6))]
    final_score = float(np.mean(top_matches))
    return round(max(0.0, min(1.0, final_score)), 6)