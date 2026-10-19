"""Application settings, loaded from environment variables or a .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ELT_", extra="ignore")

    app_name: str = "Employee Login Location Tracking & Shift Monitoring"
    database_url: str = "sqlite:///./elt.db"

    # Security
    secret_key: str = "change-me-in-production-use-a-64-char-random-string"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    login_rate_limit_per_minute: int = 20  # per client IP
    cors_origins: str = ""  # comma-separated; empty = same-origin only

    # Business rules
    timezone: str = "Asia/Kolkata"
    nearest_city_max_km: float = 60.0
    poor_gps_accuracy_m: float = 1500.0
    impossible_travel_kmh: float = 900.0
    retention_days: int = 365
    overtime_threshold_minutes: int = 30
    max_session_hours: int = 20  # an open sign-in older than this can't be checked out

    # Optional external IP geolocation (off by default; sends IPs to a third party)
    ip_geo_provider: str = "none"  # "none" | "ipapi"
    ip_geo_timeout_s: float = 2.0

    # ---- Notifications ----
    public_url: str = "http://localhost:8000"   # used for links in messages
    company_name: str = ""             # e.g. "Acme India"; shown in messages
    # Email: "console" logs messages and marks them sent (development), "smtp" really sends, "none" disables.
    email_backend: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""                # e.g. "Attendance <attendance@yourcompany.in>"
    smtp_starttls: bool = True         # port 587
    smtp_ssl: bool = False             # port 465
    smtp_timeout_s: float = 10.0
    # SMS / WhatsApp via your gateway: JSON POST {"to", "message", "kind"} to this URL. Empty = disabled.
    sms_webhook_url: str = ""
    sms_webhook_token: str = ""        # sent as "Authorization: Bearer <token>"
    # What to send
    notify_employee_on_login: bool = True
    notify_manager_on_login: bool = True
    manager_notify_mode: str = "all"   # "all" every sign-in | "exceptions" only late/outside shift/flagged
    notify_on_lockout: bool = True
    notify_cooldown_minutes: int = 30  # skip repeat routine sign-in messages within this window
    include_coordinates: bool = False  # add GPS coordinates to messages (city/state is always included)
    notify_max_attempts: int = 3

    # Trust X-Forwarded-For only when running behind your own reverse proxy
    trust_proxy_headers: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
