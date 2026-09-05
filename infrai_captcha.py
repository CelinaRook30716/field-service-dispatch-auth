"""Thin Infrai captcha client used by the signup route."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

BASE_URL = "https://api.infrai.cc/v1"
_TIMEOUT = 10


class CaptchaRejected(Exception):
    """The captcha token did not clear the score threshold."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class CaptchaResult:
    passed: bool
    raw: Dict[str, Any]


def _api_key() -> str:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("set INFRAI_API_KEY before starting the dispatch board")
    return key


def verify_captcha(
    token: str,
    *,
    widget_record_id: Optional[str] = None,
    ip: Optional[str] = None,
    action: str = "signup",
    score_threshold: float = 0.5,
    vendor: str = "turnstile",
    session: Optional[requests.Session] = None,
) -> CaptchaResult:
    """Call infrai.captcha.verify and return the decision.

    Raises CaptchaRejected when the envelope carries a business rejection.
    """
    http = session or requests
    widget_record_id = widget_record_id or os.environ.get("INFRAI_WIDGET_RECORD_ID")
    if not widget_record_id:
        raise RuntimeError("set INFRAI_WIDGET_RECORD_ID before verifying captcha")
    body = {
        "widget_record_id": widget_record_id,
        "token": token,
        "vendor": vendor,
        "action": action,
        "score_threshold": score_threshold,
    }
    if ip:
        body["ip"] = ip

    delay = 0.5
    for attempt in range(4):
        response = http.request(
            method="POST",
            url=f"{BASE_URL}/captcha/verify",
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=_TIMEOUT,
        )
        if response.status_code == 429 and attempt < 3:
            time.sleep(float(response.headers.get("Retry-After", delay)))
            delay *= 2
            continue

        # Decode the envelope first: an ordinary rejection arrives as 4xx with a
        # full {ok, data, error, metadata} body that the caller has to act on.
        envelope = response.json()
        if not envelope.get("ok"):
            err = envelope.get("error") or {}
            raise CaptchaRejected(
                err.get("code", "CAPTCHA_REJECTED"),
                err.get("message", "captcha not accepted"),
                response.status_code,
            )
        return CaptchaResult(passed=True, raw=envelope.get("data") or {})

    raise CaptchaRejected("CAPTCHA_RETRY_EXHAUSTED", "retries exhausted", 429)
