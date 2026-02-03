from pydantic import BaseModel, Field
from typing import Optional


class AdminLoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None


class ClientLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str  # "admin" or "client"
    expires_in: int


class AdminUserResponse(BaseModel):
    id: int
    username: str
    has_totp: bool
    is_active: bool

    model_config = {"from_attributes": True}
