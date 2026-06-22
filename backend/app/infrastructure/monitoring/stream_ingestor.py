# stream_ingestor.py
import logging
import platform
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generator

import cv2

from app.infrastructure.monitoring.capture_device_service import resolve_hdmi_source

logger = logging.getLogger("dtv.stream_ingestor")


@dataclass
class StreamFrame:
    frame_index: int
    fps: float
    timestamp_seconds: float
    frame: Any
    channel_id: int | None
    source_id: str
    ingest_wallclock_utc: str
    source_wallclock_utc: str
    retry_count: int


def open_capture(source: int | str) -> cv2.VideoCapture:
    if platform.system().lower() == "windows" and isinstance(source, int):
        capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    else:
        capture = cv2.VideoCapture(source)

    return capture


class HDMICaptureAdapter:
    def __init__(self, input_identifier: str | int):
        self.input_identifier = input_identifier
        self.capture: cv2.VideoCapture | None = None

    def open(self) -> cv2.VideoCapture:
        source = (
            self.input_identifier
            if isinstance(self.input_identifier, int)
            else resolve_hdmi_source(self.input_identifier)
        )

        capture = open_capture(source)

        if not capture.isOpened():
            raise RuntimeError(
                f"Failed to open HDMI capture device '{self.input_identifier}'. "
                "On Windows, close VLC/OBS/Camera app first. "
                "If using Docker Desktop, run the ingestion worker on the Windows host instead of inside Docker."
            )

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)

        self.capture = capture
        return capture

    def close(self) -> None:
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception:
                logger.exception("hdmi_capture_release_failed")
            self.capture = None


class StreamIngestor:
    """
    HDMI-only frame ingestor.

    On Windows, this uses DirectShow because many HDMI USB capture cards fail with MSMF.
    """

    def __init__(
        self,
        *,
        input_identifier: str | int,
        channel_id: int | None = None,
        source_id: str | None = None,
        reconnect_delay_seconds: float = 5.0,
        max_retries: int = -1,
    ):
        self.input_identifier = input_identifier
        self.channel_id = channel_id
        self.source_id = source_id or str(input_identifier)
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self.max_retries = max_retries

    def frame_generator(self) -> Generator[StreamFrame, None, None]:
        retries = 0
        total_frames_seen = 0

        while True:
            adapter = HDMICaptureAdapter(self.input_identifier)

            try:
                logger.info(
                    "opening_hdmi_capture channel_id=%s input_identifier=%s retries=%s",
                    self.channel_id,
                    self.input_identifier,
                    retries,
                )

                capture = adapter.open()

                fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
                if fps <= 0:
                    fps = 25.0

                frame_index = 0
                connection_start_wallclock = time.time()

                while True:
                    success, frame = capture.read()

                    if not success or frame is None:
                        raise RuntimeError("HDMI capture interrupted or returned empty frame")

                    now_utc = datetime.now(timezone.utc)
                    elapsed = max(time.time() - connection_start_wallclock, 0.0)
                    timestamp_seconds = max(frame_index / fps, elapsed)

                    yield StreamFrame(
                        frame_index=frame_index,
                        fps=fps,
                        timestamp_seconds=timestamp_seconds,
                        frame=frame,
                        channel_id=self.channel_id,
                        source_id=self.source_id,
                        ingest_wallclock_utc=now_utc.isoformat(),
                        source_wallclock_utc=now_utc.isoformat(),
                        retry_count=retries,
                    )

                    frame_index += 1
                    total_frames_seen += 1

            except Exception as exc:
                logger.warning(
                    "hdmi_capture_error channel_id=%s input_identifier=%s retries=%s total_frames=%s error=%s",
                    self.channel_id,
                    self.input_identifier,
                    retries,
                    total_frames_seen,
                    str(exc),
                )

                retries += 1

                if self.max_retries >= 0 and retries > self.max_retries:
                    logger.error(
                        "hdmi_capture_max_retries_exceeded channel_id=%s input_identifier=%s",
                        self.channel_id,
                        self.input_identifier,
                    )
                    break

                time.sleep(self.reconnect_delay_seconds)

            finally:
                adapter.close()