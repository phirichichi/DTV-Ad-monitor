#backend/app/infrastructure/monitoring/capture_device_service.py
import logging
import platform
from dataclasses import dataclass
from pathlib import Path 
from tempfile import NamedTemporaryFile

import cv2
logger = logging.getLogger("dtv.capture_device_service")
# Optional dependency for Windows device names
try:
    from pygrabber.dshow_graph import FilterGraph
    PYGRABBER_AVAILABLE = True
except ImportError:
    PYGRABBER_AVAILABLE = False
@dataclass
class CaptureProbeResult:
    input_identifier: str
    device_name: str | None
    opened: bool
    frame_captured: bool
    width: int | None
    height: int | None
    fps: float | None
    message: str

def get_windows_video_devices() -> list[str]:
    """
    Returns friendly DirectShow device names.
    Example:
    [
        "USB Video",
        "HP Webcam",
        "OBS Virtual Camera"
    ]
    """
    if platform.system().lower() != "windows":
        return []

    if not PYGRABBER_AVAILABLE:
        logger.warning(
            "pygrabber_not_installed_windows_device_names_unavailable"
        )
        return []

    try:
        graph = FilterGraph()
        return graph.get_input_devices()
    except Exception as exc:
        logger.exception(
            "failed_to_enumerate_directshow_devices error=%s",
            str(exc),
        )
        return []

def resolve_hdmi_source(input_identifier: str) -> int | str:
    raw = input_identifier.strip()

    if raw.isdigit():
        return int(raw)
    return raw

def open_capture(source: int | str) -> cv2.VideoCapture:
    """
    Opens HDMI capture source.
    Windows:
        cv2.VideoCapture(index, cv2.CAP_DSHOW)
    Linux/Mac:
        cv2.VideoCapture(index)
    """
    if platform.system().lower() == "windows":
        if isinstance(source, int):
            return cv2.VideoCapture(source, cv2.CAP_DSHOW)

    return cv2.VideoCapture(source)

def get_device_name_for_index(index: int) -> str | None:
    """
    Maps OpenCV index -> DirectShow friendly name.
    Example:
        0 -> USB Video
        1 -> HP Webcam
    """
    devices = get_windows_video_devices()
    if index < len(devices):
        return devices[index]
    return None

def probe_capture_device(input_identifier: str) -> CaptureProbeResult:
    source = resolve_hdmi_source(input_identifier)
    device_name = None

    if isinstance(source, int):
        device_name = get_device_name_for_index(source)

    capture = open_capture(source)

    if not capture.isOpened():
        return CaptureProbeResult(
            input_identifier=input_identifier,
            device_name=device_name,
            opened=False,
            frame_captured=False,
            width=None,
            height=None,
            fps=None,
            message=(
                "Failed to open HDMI capture device. "
                "Close VLC, OBS, Camera app, or any software currently using the device. "
                "Docker containers typically cannot access Windows USB capture devices."
            ),
        )

    try:
        success, frame = capture.read()
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or None

        if success and frame is not None:
            return CaptureProbeResult(
                input_identifier=input_identifier,
                device_name=device_name,
                opened=True,
                frame_captured=True,
                width=width,
                height=height,
                fps=fps,
                message="Capture device opened and frame captured successfully.",
            )

        return CaptureProbeResult(
            input_identifier=input_identifier,
            device_name=device_name,
            opened=True,
            frame_captured=False,
            width=width,
            height=height,
            fps=fps,
            message="Capture device opened but no frame was captured.",
        )

    finally:
        capture.release()

def scan_capture_devices(max_index: int = 10) -> list[CaptureProbeResult]:
    """
    Enumerate all available capture devices.
    Windows:
        Uses DirectShow names when available.
    Linux/Mac:
        Falls back to OpenCV index scanning.
    """

    results: list[CaptureProbeResult] = []
    device_names = get_windows_video_devices()
    # Preferred path for Windows
    if device_names:
        logger.info(
            "found_directshow_devices count=%s",
            len(device_names),
        )

        for index, device_name in enumerate(device_names):
            try:
                result = probe_capture_device(str(index))
                result.device_name = device_name
                results.append(result)
            except Exception as exc:
                logger.exception(
                    "capture_device_probe_failed index=%s",
                    index,
                )

                results.append(
                    CaptureProbeResult(
                        input_identifier=str(index),
                        device_name=device_name,
                        opened=False,
                        frame_captured=False,
                        width=None,
                        height=None,
                        fps=None,
                        message=f"Probe failed: {str(exc)}",
                    )
                )
        return results

    # Fallback scanning
    logger.info(
        "falling_back_to_opencv_index_scan max_index=%s",
        max_index,
    )

    for index in range(max_index):
        try:
            results.append(
                probe_capture_device(str(index))
            )

        except Exception as exc:
            logger.exception(
                "capture_device_probe_failed index=%s",
                index,
            )

            results.append(
                CaptureProbeResult(
                    input_identifier=str(index),
                    device_name=None,
                    opened=False,
                    frame_captured=False,
                    width=None,
                    height=None,
                    fps=None,
                    message=f"Probe failed: {str(exc)}",
                )
            )
    return results

def capture_snapshot_to_temp_file(
    input_identifier: str,
) -> Path:
    source = resolve_hdmi_source(input_identifier)
    capture = open_capture(source)
    if not capture.isOpened():
        raise RuntimeError(
            "Could not open HDMI capture device"
        )

    try:
        success, frame = capture.read()
        if not success or frame is None:
            raise RuntimeError(
                "Could not capture HDMI frame"
            )

        with NamedTemporaryFile(
            suffix=".jpg",
            delete=False,
        ) as tmp:
            temp_path = Path(tmp.name)
        saved = cv2.imwrite(
            str(temp_path),
            frame,
        )
        if not saved:
            raise RuntimeError(
                "Failed to encode HDMI snapshot"
            )
        return temp_path
    finally:
        capture.release()