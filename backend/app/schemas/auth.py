#auth.py 
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    email: EmailStr


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool