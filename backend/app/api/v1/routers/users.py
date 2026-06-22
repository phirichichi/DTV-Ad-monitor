from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.dependencies import require_roles
from app.infrastructure.db.session import get_db
from app.models import AuditLog, Role, User, UserLoginHistory

router = APIRouter(prefix="/users", tags=["Users"])


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role_name: str
    is_active: bool = True

    @field_validator("role_name")
    @classmethod
    def validate_role_name(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"admin", "operator", "client"}:
            raise ValueError("role_name must be admin, operator, or client")
        return value


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: Optional[str] = None
    is_active: bool
    last_login_at: Optional[str] = None
    current_session_active: Optional[bool] = None
    current_session_started_at: Optional[str] = None

    class Config:
        from_attributes = True


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role.name if user.role else None,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        current_session_active=user.current_session_active,
        current_session_started_at=(
            user.current_session_started_at.isoformat()
            if user.current_session_started_at
            else None
        ),
    )


@router.get("/admin-only")
def admin_only_test(current_user: User = Depends(require_roles("admin"))):
    return {
        "message": "Admin access granted",
        "user": current_user.email,
        "role": current_user.role.name if current_user.role else None,
    }


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    role = db.query(Role).filter(Role.name == payload.role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role name")

    user = User(
        email=str(payload.email),
        password_hash=get_password_hash(payload.password),
        role_id=role.id,
        is_active=payload.is_active,
        current_session_active=False,
    )

    db.add(user)
    db.flush()

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="CREATE_USER",
            entity_type="user",
            entity_id=user.id,
            details=f"Created user {user.email} with role {role.name}",
        )
    )

    db.commit()
    db.refresh(user)

    return _user_to_response(user)


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_to_response(user) for user in users]


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    user.is_active = payload.is_active

    if not payload.is_active:
        user.current_session_active = False

        db.query(UserLoginHistory).filter(
            UserLoginHistory.user_id == user.id,
            UserLoginHistory.is_current_session.is_(True),
        ).update(
            {
                "is_current_session": False,
                "logout_at": datetime.now(timezone.utc),
            }
        )

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="UPDATE_USER_STATUS",
            entity_type="user",
            entity_id=user.id,
            details=f"Set user {user.email} active={payload.is_active}",
        )
    )

    db.commit()
    db.refresh(user)

    return _user_to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="DELETE_USER",
            entity_type="user",
            entity_id=user.id,
            details=f"Deleted user {user.email}",
        )
    )

    db.delete(user)
    db.commit()

    return None


@router.get("/{user_id}/login-history")
def get_user_login_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    history = (
        db.query(UserLoginHistory)
        .filter(UserLoginHistory.user_id == user_id)
        .order_by(UserLoginHistory.login_at.desc())
        .limit(100)
        .all()
    )

    return {
        "user_id": user.id,
        "email": user.email,
        "history": [
            {
                "id": row.id,
                "login_at": row.login_at.isoformat() if row.login_at else None,
                "logout_at": row.logout_at.isoformat() if row.logout_at else None,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "is_current_session": row.is_current_session,
            }
            for row in history
        ],
    }