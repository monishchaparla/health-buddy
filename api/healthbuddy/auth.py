"""Passwords (argon2id), opaque session tokens stored as SHA-256, HTTP-only cookie or bearer token."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response

from healthbuddy.db import get_conn

COOKIE = "healthbuddy_session"
SESSION_DAYS = 30
_ph = PasswordHasher()
_DUMMY_HASH = _ph.hash("timing-equaliser")
# shortcut: in-memory throttle keyed on (email, client IP), per process; move to Redis/DB for multi-instance.
# Keying on IP too means an attacker elsewhere can't lock a real user out of their own account. The client IP
# comes from X-Forwarded-For, which a client can rotate, so a looser per-email cap backs it up.
_failures: dict[str, list[float]] = {}
_known_ips: dict[str, set[str]] = {}  # IPs that signed in to this email before skip the per-email cap
MAX_FAILURES, MAX_PER_EMAIL, MAX_HARD, WINDOW_S = 5, 20, 100, 15 * 60  # MAX_HARD applies to every IP


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw_hash: str | None, pw: str) -> bool:
    try:
        return _ph.verify(pw_hash or _DUMMY_HASH, pw) and pw_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _recent(key: str) -> int:
    now = time.time()
    _failures[key] = [t for t in _failures.get(key, []) if now - t < WINDOW_S]
    return len(_failures[key])


def throttled(email: str, ip: str) -> bool:
    if _recent(f"{email}|{ip}") >= MAX_FAILURES or _recent(email) >= MAX_HARD:
        return True
    return ip not in _known_ips.get(email, set()) and _recent(email) >= MAX_PER_EMAIL


def record_failure(email: str, ip: str) -> None:
    for key in (f"{email}|{ip}", email):
        _failures.setdefault(key, []).append(time.time())


def clear_failures(email: str, ip: str) -> None:
    """Called on a successful login."""
    _failures.pop(f"{email}|{ip}", None)
    _known_ips.setdefault(email, set()).add(ip)


def create_session(conn: sqlite3.Connection, user_id: int, kind: str = "web") -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    conn.execute("INSERT INTO sessions (token_hash, user_id, kind, expires_at) VALUES (?, ?, ?, ?)",
                 (_digest(token), user_id, kind, expires))
    return token


def set_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
                        secure=os.environ.get("HEALTHBUDDY_COOKIE_INSECURE", "0") != "1", path="/")  # http dev only: HEALTHBUDDY_COOKIE_INSECURE=1


def end_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))


def token_from(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE)


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> sqlite3.Row:
    token = token_from(request)
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    row = conn.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
        (_digest(token), datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    if row is None:
        raise HTTPException(401, "Your session expired. Sign in again.")
    return row
