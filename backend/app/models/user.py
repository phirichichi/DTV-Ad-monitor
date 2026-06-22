#user.py 
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    current_session_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_session_started_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    role = relationship("Role", back_populates="users")