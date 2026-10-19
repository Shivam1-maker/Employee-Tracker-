"""Pydantic request/response schemas."""
from __future__ import annotations

import ipaddress
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import Role


def _norm_phone(v):
    """Accept common Indian formats and normalise to E.164: 98765 43210 -> +919876543210."""
    if v is None:
        return None
    digits = "".join(ch for ch in str(v) if ch.isdigit() or ch == "+")
    if not digits:
        return None
    if digits.startswith("+"):
        return digits
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "+91" + digits[1:]
    return digits  # fails the pattern check with a clear message


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=254, description="Employee code or email")
    password: str = Field(min_length=1, max_length=128)
    location_consent: bool = False
    location: LocationIn | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    login_event_id: int
    verification_status: str
    shift_status: str | None


class ShiftBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start_time: time
    end_time: time
    grace_minutes: int = Field(default=10, ge=0, le=240)
    early_window_minutes: int = Field(default=60, ge=0, le=720)
    working_days: list[int] = Field(default=[0, 1, 2, 3, 4], description="Monday=0 … Sunday=6")

    @field_validator("working_days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if not v or any(d < 0 or d > 6 for d in v):
            raise ValueError("working_days must contain values 0-6")
        return sorted(set(v))


class ShiftCreate(ShiftBase):
    pass


class ShiftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    start_time: time | None = None
    end_time: time | None = None
    grace_minutes: int | None = Field(default=None, ge=0, le=240)
    early_window_minutes: int | None = Field(default=None, ge=0, le=720)
    working_days: list[int] | None = None


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    start_time: time
    end_time: time
    grace_minutes: int
    early_window_minutes: int
    working_days: list[int]

    @field_validator("working_days", mode="before")
    @classmethod
    def _parse(cls, v):
        if isinstance(v, str):
            return [int(d) for d in v.split(",") if d.strip()]
        return v


class OfficeBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=6, le=37.6)
    longitude: float = Field(ge=68, le=97.5)
    radius_m: float = Field(default=300, ge=25, le=5000)
    ip_cidrs: list[str] = Field(default_factory=list)

    @field_validator("ip_cidrs")
    @classmethod
    def _cidrs(cls, v: list[str]) -> list[str]:
        for c in v:
            ipaddress.ip_network(c, strict=False)  # raises ValueError if invalid
        return v


class OfficeCreate(OfficeBase):
    pass


class OfficeUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    state: str | None = None
    latitude: float | None = Field(default=None, ge=6, le=37.6)
    longitude: float | None = Field(default=None, ge=68, le=97.5)
    radius_m: float | None = Field(default=None, ge=25, le=5000)
    ip_cidrs: list[str] | None = None

    @field_validator("ip_cidrs")
    @classmethod
    def _cidrs(cls, v):
        for c in v or []:
            ipaddress.ip_network(c, strict=False)
        return v


class OfficeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    city: str
    state: str
    latitude: float
    longitude: float
    radius_m: float
    ip_cidrs: list[str]

    @field_validator("ip_cidrs", mode="before")
    @classmethod
    def _parse(cls, v):
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: Role = Role.EMPLOYEE
    department: str | None = Field(default=None, max_length=80)
    shift_id: int | None = None
    office_id: int | None = None
    manager_id: int | None = None
    phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$", description="E.164 format, e.g. +919876543210")

    @field_validator("phone", mode="before")
    @classmethod
    def _phone(cls, v):
        return _norm_phone(v)


class EmployeeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=10, max_length=128)
    role: Role | None = None
    department: str | None = Field(default=None, max_length=80)
    shift_id: int | None = None
    office_id: int | None = None
    is_active: bool | None = None
    manager_id: int | None = None
    phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$", description="E.164 format, e.g. +919876543210")

    @field_validator("phone", mode="before")
    @classmethod
    def _phone(cls, v):
        return _norm_phone(v)


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_code: str
    full_name: str
    email: str
    role: str
    department: str | None
    is_active: bool
    shift_id: int | None
    office_id: int | None
    location_consent_at: datetime | None
    locked_until: datetime | None
    manager_id: int | None = None
    phone: str | None = None


class LoginEventOut(BaseModel):
    id: int
    occurred_at: datetime
    occurred_at_local: str
    success: bool
    failure_reason: str | None
    employee_id: int | None
    employee_code: str | None
    employee_name: str | None
    attempted_identifier: str
    ip_address: str | None
    location_source: str
    latitude: float | None
    longitude: float | None
    accuracy_m: float | None
    city: str | None
    state: str | None
    office_name: str | None
    distance_to_office_m: float | None
    verification_status: str
    risk_flags: list[str]
    shift_name: str | None
    scheduled_start_local: str | None
    shift_status: str | None
    minutes_late: int | None
    scheduled_end_local: str | None = None
    checked_out_at_local: str | None = None
    checkout_status: str | None = None
    minutes_worked: int | None = None
    early_leave_minutes: int | None = None
    overtime_minutes: int | None = None
    review_status: str | None = None
    review_note: str | None = None


class Page(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LoginEventOut]


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int | None
    action: str
    detail: str
    ip_address: str | None
    created_at: datetime


class CheckoutResponse(BaseModel):
    login_event_id: int
    checked_out_at_local: str
    checkout_status: str
    minutes_worked: int
    early_leave_minutes: int | None
    overtime_minutes: int | None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class ReviewIn(BaseModel):
    status: Literal["acknowledged", "dismissed", "open"]
    note: str = Field(default="", max_length=1000)


class HolidayIn(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=120)
    state: str | None = Field(default=None, max_length=80)


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    day: date
    name: str
    state: str | None


class LeaveIn(BaseModel):
    start_date: date
    end_date: date
    leave_type: Literal["casual", "sick", "earned", "comp_off", "unpaid", "other"] = "casual"
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 90:
            raise ValueError("A single request can cover at most 90 days")
        return self


class LeaveDecision(BaseModel):
    status: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=1000)


class LeaveOut(BaseModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    start_date: date
    end_date: date
    days: int
    leave_type: str
    reason: str
    status: str
    review_note: str | None
    created_at: datetime


class ImportRequest(BaseModel):
    csv: str = Field(min_length=1, max_length=2_000_000)
    dry_run: bool = False


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    channel: str
    recipient: str
    recipient_user_id: int | None
    about_user_id: int | None
    login_event_id: int | None
    subject: str
    body: str
    status: str
    error: str | None
    attempts: int
    created_at: datetime
    sent_at: datetime | None


class TestNotification(BaseModel):
    channel: Literal["email", "sms"] = "email"
    to: str = Field(min_length=3, max_length=254, description="Email address or phone number")
