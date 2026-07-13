#backend/app/models/__init__.py
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.db.session import Base
from app.models.role import Role
from app.models.user import User

class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    input_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    capture_card_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    main_channel_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capture_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="unknown",
    )
    last_heartbeat_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    last_interruption_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    last_interruption_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    detections = relationship("AdDetectionLog", back_populates="channel")

class Advertiser(Base):
    __tablename__ = "advertisers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    contract_start_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    advertisements = relationship("Advertisement", back_populates="advertiser")

class Advertisement(Base):
    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="commercial")
    reference_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_audio_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_frame_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uploaded_file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    advertiser = relationship("Advertiser", back_populates="advertisements")
    detections = relationship("AdDetectionLog", back_populates="advertisement")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User")

class AdDetectionLog(Base):
    __tablename__ = "ad_detection_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    advertisement_id: Mapped[int | None] = mapped_column(
        ForeignKey("advertisements.id"),
        nullable=True,
    )

    detected_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_sections_matched: Mapped[str | None] = mapped_column(Text, nullable=True)
    frame_sections_matched: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="matched")
    match_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    channel = relationship("Channel", back_populates="detections")
    advertisement = relationship("Advertisement", back_populates="detections")
    evidence_items = relationship(
        "DetectionEvidence",
        back_populates="detection",
        cascade="all, delete-orphan",
    )

class DetectionEvidence(Base):
    __tablename__ = "detection_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    detection_id: Mapped[int] = mapped_column(
        ForeignKey("ad_detection_logs.id"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    detection = relationship("AdDetectionLog", back_populates="evidence_items")

class UserLoginHistory(Base):
    __tablename__ = "user_login_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    login_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), index=True)
    logout_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_current_session: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user = relationship("User")

class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_date: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
    )
    report_start: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
    )
    report_end: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
    )
    generated_at: Mapped[DateTime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    total_detections: Mapped[int] = mapped_column(Integer,
        default=0,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

__all__ = [
    "Role",
    "User",
    "Channel",
    "Advertiser",
    "Advertisement",
    "AuditLog",
    "AdDetectionLog",
    "DetectionEvidence",
    "DailyReport",
    "UserLoginHistory",
]