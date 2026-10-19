"""Password hashing, JWT tokens, client IP extraction and rate limiting."""
from __future__ import annotations

import threading
import time as _time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Request

from app.config import get_settings

# A real bcrypt hash used to keep timing constant when the user does not exist.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], (password_hash or _DUMMY_HASH).encode())
    except ValueError:
        return False


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    s = get_settings()
    expires_in = s.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm), expires_in


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.secret_key, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub"]})


def client_ip(request: Request) -> str | None:
    if get_settings().trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


class SlidingWindowLimiter:
    """In-process limiter. For multi-instance deployments, back this with Redis."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        now = _time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = SlidingWindowLimiter()
