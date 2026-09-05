"""Run the whole shift against a live server: signup -> claim -> photo -> close.

    INFRAI_API_KEY=... python dispatch_board.py      # terminal 1
    CAPTCHA_TOKEN=... python walkthrough.py          # terminal 2
"""
from __future__ import annotations

import os
import sys

import requests

BASE = os.environ.get("BOARD_URL", "http://127.0.0.1:5000")


def main() -> int:
    token = os.environ.get("CAPTCHA_TOKEN")
    if not token:
        print("set CAPTCHA_TOKEN to the widget token from your signup form")
        return 1

    http = requests.Session()
    signup = http.request(
        method="POST",
        url=f"{BASE}/signup",
        json={"email": "rosa@fieldsvc.test", "password": "torque-wrench-7",
              "full_name": "Rosa Iglesias", "captcha_token": token},
        timeout=15,
    )
    print("signup", signup.status_code, signup.json())
    if signup.status_code >= 400:
        return 1

    for call in (
        ("POST", "/work-orders/WO-4471/claim", None),
        ("POST", "/work-orders/WO-4471/photos",
         {"key": "wo-4471/compressor-plate.jpg", "caption": "nameplate after swap"}),
        ("POST", "/work-orders/WO-4471/close", {"follow_up_note": "monitor amp draw next week"}),
        ("GET", "/work-orders", None),
    ):
        method, path, body = call
        res = http.request(method=method, url=f"{BASE}{path}", json=body, timeout=15)
        print(method, path, res.status_code, res.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
