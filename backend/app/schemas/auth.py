import uuid
from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserSignup(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.member


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
