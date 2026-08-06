"""
Request/response schemas for trip management: create/edit/archive trips,
generate invites, and join via code.
"""
import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.trip import TripStatus
from app.models.trip_member import MemberRole, MemberStatus


class CreateTripRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    base_currency: str = Field(min_length=3, max_length=3)
    budget: float | None = Field(default=None, ge=0)
    cover_photo_url: str | None = None
    description: str | None = None

    @field_validator("base_currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start is not None and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class UpdateTripRequest(BaseModel):
    """All fields optional -- a PATCH only sends what's changing."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    destination: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    budget: float | None = Field(default=None, ge=0)
    cover_photo_url: str | None = None
    description: str | None = None


class TripResponse(BaseModel):
    id: uuid.UUID
    created_by: uuid.UUID
    name: str
    destination: str
    start_date: date
    end_date: date
    base_currency: str
    budget: float | None
    cover_photo_url: str | None
    description: str | None
    status: TripStatus

    model_config = {"from_attributes": True}


class TripMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    role: MemberRole
    status: MemberStatus

    model_config = {"from_attributes": True}


class InviteResponse(BaseModel):
    code: str
    link_token: str
    expires_at: str

    model_config = {"from_attributes": True}


class JoinTripRequest(BaseModel):
    code: str = Field(min_length=8, max_length=8)