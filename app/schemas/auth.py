"""
Request/response schemas for the auth endpoints.

Kept separate from ORM models on purpose (never expose the ORM model
directly) so we control exactly what leaves the API -- e.g. password_hash
must never be serializable, even by accident.
"""

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    
    @field_validator("password")
    @classmethod
    def password_complezity(cls, v:str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least on digit")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least on letter")
        return v
    
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    
class RefreshRequest(BaseModel):
    refresh_token: str
    
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    
class UserResponse(BaseModel):
    id: uuid.UUID
    email: str | None
    display_name: str
    avatar_url: str | None
    
    model_config = {"from_attributes": True}
    
class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse
    
    