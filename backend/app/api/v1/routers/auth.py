from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.dependencies import get_current_user
from app.infrastructure.db.session import get_db
from app.models import AuditLog, User, UserLoginHistory
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedException("Invalid email or password")

    if not user.is_active:
        raise UnauthorizedException("User account is inactive")

    if not user.role:
        raise UnauthorizedException("User does not have an assigned role")

    access_token = create_access_token(subject=user.email, role=user.role.name)
    refresh_token = create_refresh_token(subject=user.email, role=user.role.name)

    now = datetime.now(timezone.utc)

    db.query(UserLoginHistory).filter(
        UserLoginHistory.user_id == user.id,
        UserLoginHistory.is_current_session.is_(True),
    ).update(
        {
            "is_current_session": False,
            "logout_at": now,
        }
    )

    db.add(
        UserLoginHistory(
            user_id=user.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            session_token=access_token[:250],
            is_current_session=True,
        )
    )

    user.last_login_at = now
    user.current_session_started_at = now
    user.current_session_active = True

    db.add(
        AuditLog(
            user_id=user.id,
            action="LOGIN",
            entity_type="user",
            entity_id=user.id,
            details=f"User {user.email} logged in",
        )
    )

    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role.name,
        email=user.email,
    )

@router.post("/refresh")
def refresh_access_token(authorization: str = Header(...)):
    try:
        token = authorization.replace("Bearer ", "").strip()
        payload = decode_token(token)

        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid refresh token")

        return {
            "access_token": create_access_token(
                subject=payload["sub"],
                role=payload["role"],
            )
        }
    except JWTError as exc:
        raise UnauthorizedException("Invalid or expired refresh token") from exc

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    db.query(UserLoginHistory).filter(
        UserLoginHistory.user_id == current_user.id,
        UserLoginHistory.is_current_session.is_(True),
    ).update(
        {
            "is_current_session": False,
            "logout_at": now,
        }
    )

    current_user.current_session_active = False

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="LOGOUT",
            entity_type="user",
            entity_id=current_user.id,
            details=f"User {current_user.email} logged out",
        )
    )

    db.commit()

    return {"status": "logged_out"}

@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: User = Depends(get_current_user)):
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role.name if current_user.role else "unknown",
        is_active=current_user.is_active,
    )