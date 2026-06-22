from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.dependencies import require_roles
from app.infrastructure.db.session import get_db
from app.infrastructure.monitoring.capture_device_service import (
    capture_snapshot_to_temp_file,
    probe_capture_device,
    scan_capture_devices,
)
from app.models import AuditLog, Channel, User

router = APIRouter(prefix="/channels", tags=["Channels"])


class ChannelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    input_identifier: str = Field(min_length=1, max_length=255)
    capture_card_name: str | None = None
    is_active: bool = True
    monitoring_enabled: bool = True
    main_channel_flag: bool = False

    @field_validator("name", "input_identifier", "capture_card_name")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ChannelUpdateRequest(BaseModel):
    name: str | None = None
    input_identifier: str | None = None
    capture_card_name: str | None = None
    is_active: bool | None = None
    monitoring_enabled: bool | None = None
    main_channel_flag: bool | None = None
    capture_status: str | None = None
    last_heartbeat_at: str | None = None
    last_interruption_at: str | None = None
    last_interruption_reason: str | None = None

    @field_validator(
        "name",
        "input_identifier",
        "capture_card_name",
        "capture_status",
        "last_interruption_reason",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ChannelHeartbeatRequest(BaseModel):
    capture_status: str = "healthy"


class ChannelResponse(BaseModel):
    id: int
    name: str

    input_identifier: str | None = None

    capture_card_name: str | None = None

    device_name: str | None = None

    is_active: bool
    monitoring_enabled: bool
    main_channel_flag: bool

    capture_status: str | None = None
    last_heartbeat_at: str | None = None
    last_interruption_at: str | None = None
    last_interruption_reason: str | None = None

    class Config:
        from_attributes = True


class ChannelProbeResponse(BaseModel):
    channel_id: int
    channel_name: str
    opened: bool
    frame_captured: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    message: str


class CaptureDeviceProbeResponse(BaseModel):
    input_identifier: str
    device_name: str | None = None
    opened: bool
    frame_captured: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    message: str


def _channel_to_response(channel: Channel) -> ChannelResponse:
    device_name = None

    try:
        devices = scan_capture_devices(max_index=10)

        matching_device = next(
            (
                device
                for device in devices
                if str(device.input_identifier) == str(channel.input_identifier)
            ),
            None,
        )

        if matching_device:
            device_name = matching_device.device_name

    except Exception:
        # Never fail channel listing because device scanning failed
        device_name = channel.capture_card_name

    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        input_identifier=channel.input_identifier,
        capture_card_name=channel.capture_card_name,
        device_name=device_name or channel.capture_card_name,
        is_active=channel.is_active,
        monitoring_enabled=channel.monitoring_enabled,
        main_channel_flag=channel.main_channel_flag,
        capture_status=channel.capture_status,
        last_heartbeat_at=channel.last_heartbeat_at.isoformat()
        if channel.last_heartbeat_at
        else None,
        last_interruption_at=channel.last_interruption_at.isoformat()
        if channel.last_interruption_at
        else None,
        last_interruption_reason=channel.last_interruption_reason,
    )


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    payload: ChannelCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing_channel = db.query(Channel).filter(Channel.name == payload.name).first()
    if existing_channel:
        raise HTTPException(status_code=400, detail="Channel already exists")

    if payload.main_channel_flag:
        db.query(Channel).update({"main_channel_flag": False})

    channel = Channel(
        name=payload.name,
        input_identifier=payload.input_identifier,
        capture_card_name=payload.capture_card_name,
        is_active=payload.is_active,
        monitoring_enabled=payload.monitoring_enabled,
        main_channel_flag=payload.main_channel_flag,
        capture_status="unknown",
        last_heartbeat_at=datetime.now(timezone.utc)
        if payload.monitoring_enabled
        else None,
    )

    db.add(channel)
    db.flush()

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="CREATE_HDMI_CHANNEL",
            entity_type="channel",
            entity_id=channel.id,
            details=(
                f"Created HDMI channel {channel.name} "
                f"input_identifier={channel.input_identifier}"
            ),
        )
    )

    db.commit()
    db.refresh(channel)
    return _channel_to_response(channel)


@router.get("/", response_model=list[ChannelResponse])
def list_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    channels = db.query(Channel).order_by(Channel.created_at.desc()).all()
    return [_channel_to_response(channel) for channel in channels]


@router.get("/monitoring-enabled", response_model=list[ChannelResponse])
def list_monitoring_enabled_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    channels = (
        db.query(Channel)
        .filter(Channel.monitoring_enabled.is_(True), Channel.is_active.is_(True))
        .order_by(Channel.created_at.desc())
        .all()
    )
    return [_channel_to_response(channel) for channel in channels]


@router.get("/capture-devices", response_model=list[CaptureDeviceProbeResponse])
def capture_devices(
    current_user: User = Depends(require_roles("admin", "operator")),
):
    results = scan_capture_devices(max_index=10)

    return [
        CaptureDeviceProbeResponse(
            input_identifier=item.input_identifier,
            device_name=item.device_name,
            opened=item.opened,
            frame_captured=item.frame_captured,
            width=item.width,
            height=item.height,
            fps=item.fps,
            message=item.message,
        )
        for item in results
    ]


@router.patch("/{channel_id}", response_model=ChannelResponse)
def update_channel(
    channel_id: int,
    payload: ChannelUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if payload.main_channel_flag:
        db.query(Channel).update({"main_channel_flag": False})

    if payload.name is not None:
        channel.name = payload.name
    if payload.input_identifier is not None:
        channel.input_identifier = payload.input_identifier
    if payload.capture_card_name is not None:
        channel.capture_card_name = payload.capture_card_name
    if payload.is_active is not None:
        channel.is_active = payload.is_active
    if payload.monitoring_enabled is not None:
        channel.monitoring_enabled = payload.monitoring_enabled
    if payload.main_channel_flag is not None:
        channel.main_channel_flag = payload.main_channel_flag
    if payload.capture_status is not None:
        channel.capture_status = payload.capture_status
    if payload.last_heartbeat_at is not None:
        channel.last_heartbeat_at = datetime.fromisoformat(payload.last_heartbeat_at)
    if payload.last_interruption_at is not None:
        channel.last_interruption_at = datetime.fromisoformat(payload.last_interruption_at)
    if payload.last_interruption_reason is not None:
        channel.last_interruption_reason = payload.last_interruption_reason

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="UPDATE_HDMI_CHANNEL",
            entity_type="channel",
            entity_id=channel.id,
            details=f"Updated HDMI channel {channel.name}",
        )
    )

    db.commit()
    db.refresh(channel)
    return _channel_to_response(channel)


@router.post("/{channel_id}/heartbeat", response_model=ChannelResponse)
def heartbeat_channel(
    channel_id: int,
    payload: ChannelHeartbeatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel.last_heartbeat_at = datetime.now(timezone.utc)
    channel.capture_status = payload.capture_status

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="HEARTBEAT_HDMI_CHANNEL",
            entity_type="channel",
            entity_id=channel.id,
            details=f"Heartbeat for HDMI channel {channel.name} status={payload.capture_status}",
        )
    )

    db.commit()
    db.refresh(channel)
    return _channel_to_response(channel)


@router.post("/{channel_id}/probe", response_model=ChannelProbeResponse)
def probe_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    result = probe_capture_device(channel.input_identifier)

    now = datetime.now(timezone.utc)
    channel.last_heartbeat_at = now
    channel.capture_status = (
        "healthy" if result.opened and result.frame_captured else "probe_failed"
    )

    if not result.opened or not result.frame_captured:
        channel.last_interruption_at = now
        channel.last_interruption_reason = result.message

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="PROBE_HDMI_CHANNEL",
            entity_type="channel",
            entity_id=channel.id,
            details=(
                f"Probe channel={channel.name} "
                f"opened={result.opened} frame_captured={result.frame_captured}"
            ),
        )
    )

    db.commit()
    db.refresh(channel)

    return ChannelProbeResponse(
        channel_id=channel.id,
        channel_name=channel.name,
        opened=result.opened,
        frame_captured=result.frame_captured,
        width=result.width,
        height=result.height,
        fps=result.fps,
        message=result.message,
    )


@router.get("/{channel_id}/snapshot")
def get_channel_snapshot(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "operator")),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        temp_path = capture_snapshot_to_temp_file(channel.input_identifier)
    except RuntimeError as exc:
        now = datetime.now(timezone.utc)
        channel.capture_status = "interrupted"
        channel.last_interruption_at = now
        channel.last_interruption_reason = str(exc)
        db.commit()

        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return FileResponse(
        path=str(temp_path),
        media_type="image/jpeg",
        filename=f"channel_{channel.id}_snapshot.jpg",
    )