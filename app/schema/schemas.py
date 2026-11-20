from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _to_naive_utc(v: datetime) -> datetime:
    if v.tzinfo is not None:
        v = v.astimezone(timezone.utc).replace(tzinfo=None)
        
    return v


# ---------- auth ----------
class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(min_length=6, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def _trim_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def _trim_email(cls, value: str) -> str:
        return value.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    is_organizer: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


# ---------- events ----------
class EventBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    location: str = Field(min_length=1, max_length=255)
    start_time: datetime
    end_time: datetime
    capacity: int = Field(gt=0)

    @field_validator("start_time", "end_time")
    @classmethod
    def _utc(cls, v):
        return _to_naive_utc(v)

    @model_validator(mode="after")
    def _order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventCreate(EventBase):
    @model_validator(mode="after")
    def _start_in_future(self):
        if self.start_time <= datetime.now(timezone.utc).replace(tzinfo=None):
            raise ValueError("start_time must be in the future")
        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, min_length=1, max_length=255)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    capacity: Optional[int] = Field(default=None, gt=0)

    @field_validator("start_time", "end_time")
    @classmethod
    def _utc(cls, v):
        return _to_naive_utc(v) if v else v

    @model_validator(mode="after")
    def _provided_values_are_not_null(self):
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class EventOut(EventBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organizer_id: Optional[int]
    spots_left: int = 0
    created_at: datetime


# ---------- registrations ----------
class RegistrationForm(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(default="", max_length=30)
    notes: str = Field(default="", max_length=2000)

    @field_validator("full_name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("phone", "notes")
    @classmethod
    def _trim_optional_strings(cls, value: str) -> str:
        return value.strip()


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    event_id: int
    event_title: str
    event_start_time: datetime
    full_name: str
    phone: str
    notes: str
    status: str
    created_at: datetime
    cancelled_at: Optional[datetime]
