"""Server-side sessions: the cookie holds an opaque id, state lives here."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional

SESSION_TTL_SECONDS = 8 * 60 * 60  # one field shift


@dataclass
class Technician:
    email: str
    full_name: Optional[str]
    password_hash: str
    salt: str


@dataclass
class Session:
    session_id: str
    email: str
    expires_at: float


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return digest.hex(), salt


class SessionStore:
    """In-process user + session store, swap for Postgres/Redis in production."""

    def __init__(self) -> None:
        self._users: Dict[str, Technician] = {}
        self._sessions: Dict[str, Session] = {}

    def create_technician(self, email: str, password: str, full_name: Optional[str]) -> Technician:
        if email in self._users:
            raise KeyError("that email already has an account")
        digest, salt = hash_password(password)
        tech = Technician(email=email, full_name=full_name, password_hash=digest, salt=salt)
        self._users[email] = tech
        return tech

    def check_password(self, email: str, password: str) -> bool:
        tech = self._users.get(email)
        if not tech:
            return False
        digest, _ = hash_password(password, tech.salt)
        return hmac.compare_digest(digest, tech.password_hash)

    def open_session(self, email: str) -> Session:
        session = Session(
            session_id=secrets.token_urlsafe(32),
            email=email,
            expires_at=time.time() + SESSION_TTL_SECONDS,
        )
        self._sessions[session.session_id] = session
        return session

    def resolve(self, session_id: Optional[str]) -> Optional[Session]:
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if not session:
            return None
        if session.expires_at < time.time():
            del self._sessions[session_id]
            return None
        return session

    def close_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


def new_cookie_secret() -> str:
    return os.environ.get("DISPATCH_COOKIE_SECRET") or secrets.token_hex(16)
