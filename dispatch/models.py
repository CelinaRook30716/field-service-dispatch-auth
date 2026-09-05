"""Typed request/state models for the dispatch board."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

DispatchStatus = Literal["unassigned", "dispatched", "on_site", "needs_follow_up", "closed"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SignupRequest:
    email: str
    password: str
    captcha_token: str
    full_name: Optional[str] = None

    @classmethod
    def parse(cls, payload: Dict[str, object]) -> "SignupRequest":
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        token = str(payload.get("captcha_token", ""))
        if "@" not in email:
            raise ValidationError("email must be a real address")
        if len(password) < 8:
            raise ValidationError("password must be at least 8 characters")
        if not token:
            raise ValidationError("captcha_token is required")
        name = payload.get("full_name")
        return cls(email=email, password=password, captcha_token=token,
                   full_name=str(name) if name else None)


@dataclass(frozen=True)
class LoginRequest:
    email: str
    password: str

    @classmethod
    def parse(cls, payload: Dict[str, object]) -> "LoginRequest":
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if not email or not password:
            raise ValidationError("email and password are required")
        return cls(email=email, password=password)


@dataclass(frozen=True)
class PhotoRef:
    key: str
    caption: str
    taken_at: str = field(default_factory=_now)


@dataclass
class WorkOrder:
    order_id: str
    site: str
    problem: str
    technician_email: Optional[str] = None
    status: DispatchStatus = "unassigned"
    photos: List[PhotoRef] = field(default_factory=list)
    follow_up_note: Optional[str] = None
    history: List[str] = field(default_factory=list)

    def to_json(self) -> Dict[str, object]:
        return {
            "order_id": self.order_id,
            "site": self.site,
            "problem": self.problem,
            "technician_email": self.technician_email,
            "status": self.status,
            "photos": [p.__dict__ for p in self.photos],
            "follow_up_note": self.follow_up_note,
            "history": self.history,
        }
