from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()

    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])