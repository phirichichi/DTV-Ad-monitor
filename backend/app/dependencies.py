#dependencies.py 
from typing import Callable
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.infrastructure.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise UnauthorizedException("Missing bearer token")

    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise UnauthorizedException("Invalid or expired token") from exc

    email = payload.get("sub")
    if not email:
        raise UnauthorizedException("Invalid token payload")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise UnauthorizedException("User not found")

    if not user.is_active:
        raise UnauthorizedException("User is inactive")

    return user

def require_roles(*allowed_roles: str) -> Callable:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.name if current_user.role else None
        if user_role not in allowed_roles:
            raise ForbiddenException()
        return current_user
    return role_checker