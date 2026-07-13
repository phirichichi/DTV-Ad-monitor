import logging
import subprocess
from pathlib import Path
logger = logging.getLogger("dtv.audio_extractor")

def extract_audio_chunk_from_stream(
    stream_url: str,
    output_wav_path: str,
    duration_seconds: float = 3.0,
    retries: int = 2,
    timeout: int = 15,
) -> str:
    if not stream_url:
        raise ValueError("stream_url is required for audio extraction")

    output_path = Path(output_wav_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        stream_url,
        "-t",
        str(duration_seconds),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_path),
    ]

    for attempt in range(retries + 1):
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout)

            if result.returncode == 0 and output_path.exists():
                return str(output_path)

            logger.warning(
                "audio_extraction_attempt_failed attempt=%s returncode=%s stderr=%s",
                attempt + 1,
                result.returncode,
                result.stderr.decode("utf-8", errors="ignore") if result.stderr else "",
            )
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg timeout during audio extraction attempt=%s", attempt + 1)

    raise RuntimeError("Audio extraction failed")