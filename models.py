"""SQLAlchemy ORM models."""
from datetime import date, datetime, time, timezone
from enum import Enum

from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
                        String, Text, Time, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class VerificationStatus(str, Enum):
    VERIFIED_OFFICE = "verified_office"      # device GPS inside an office geofence
    VERIFIED_NETWORK = "verified_network"    # IP inside a registered office network
    APPROXIMATE = "approximate"              # located, but low precision (poor GPS or IP lookup)
    OFFSITE = "offsite"                      # precise GPS, not at any office (e.g. remote work)
    OUTSIDE_INDIA = "outside_india"          # coordinates fall outside India
    UNVERIFIED = "unverified"                # no consent / no location signal


class ShiftStatus(str, Enum):
    ON_TIME = "on_time"
    LATE = "late"
    OUTSIDE_SHIFT = "outside_shift"
    OFF_DAY = "off_day"
    HOLIDAY = "holiday"
    ON_LEAVE = "on_leave"
    NO_SHIFT = "no_shift"


class CheckoutStatus(str, Enum):
    COMPLETED = "completed"        # left at or after shift end, within overtime threshold
    EARLY_LEAVE = "early_leave"
    OVERTIME = "overtime"
    UNSCHEDULED = "unscheduled"    # no scheduled shift to compare with


class ReviewStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"  # looked at, legitimate concern noted
    DISMISSED = "dismissed"        # false positive


class LeaveStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)  # end <= start means overnight shift
    grace_minutes: Mapped[int] = mapped_column(Integer, default=10)
    early_window_minutes: Mapped[int] = mapped_column(Integer, default=60)
    working_days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4")  # Mon=0
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def working_day_set(self) -> set[int]:
        return {int(d) for d in self.working_days.split(",") if d.strip() != ""}


class Office(Base):
    __tablename__ = "offices"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[float] = mapped_column(Float, default=300.0)
    ip_cidrs: Mapped[str] = mapped_column(Text, default="")  # comma-separated CIDRs
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default=Role.EMPLOYEE.value)
    department: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    office_id: Mapped[int | None] = mapped_column(ForeignKey("offices.id", ondelete="SET NULL"), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)  # E.164, e.g. +919876543210

    shift: Mapped[Shift | None] = relationship(lazy="joined")
    office: Mapped[Office | None] = relationship(lazy="joined")
    manager: Mapped["User | None"] = relationship(remote_side="User.id", lazy="select", foreign_keys=[manager_id])


class LoginEvent(Base):
    __tablename__ = "login_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    attempted_identifier: Mapped[str] = mapped_column(String(254))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    failure_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_source: Mapped[str] = mapped_column(String(20), default="none")  # gps | network | ip | none
    city: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    office_id: Mapped[int | None] = mapped_column(ForeignKey("offices.id", ondelete="SET NULL"), nullable=True)
    distance_to_office_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), default=VerificationStatus.UNVERIFIED.value, index=True)
    risk_flags: Mapped[str] = mapped_column(String(200), default="")

    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    shift_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shift_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    minutes_late: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Check-out (sign-out) of this session
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    minutes_worked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    early_leave_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overtime_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkout_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Alert review workflow for flagged events
    review_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(lazy="joined", foreign_keys=[user_id])
    office: Mapped[Office | None] = relationship(lazy="joined")

    __table_args__ = (Index("ix_login_user_time", "user_id", "occurred_at"),)


class Holiday(Base):
    __tablename__ = "holidays"
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    name: Mapped[str] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)  # None = applies across India
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("day", "state", name="uq_holiday_day_state"),)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    leave_type: Mapped[str] = mapped_column(String(30), default="casual")
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=LeaveStatus.PENDING.value, index=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(lazy="joined", foreign_keys=[user_id])


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class Notification(Base):
    """Outbox: every email/SMS the system tries to send, with its delivery result."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)  # login_employee, login_manager, account_locked, test
    channel: Mapped[str] = mapped_column(String(20))           # email | sms
    recipient_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient: Mapped[str] = mapped_column(String(254))        # email address or phone number
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text)
    login_event_id: Mapped[int | None] = mapped_column(ForeignKey("login_events.id", ondelete="SET NULL"), nullable=True)
    about_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=NotificationStatus.PENDING.value, index=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
